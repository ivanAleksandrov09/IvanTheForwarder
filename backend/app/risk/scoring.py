"""Explainable client risk scoring. Owner: B.

score = BASE + sum(factor.impact), clamped to 0..100. Each factor carries a sentence with the numbers
and EvidenceRefs to its source records. No black-box numbers.
"""

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.core.formatting import format_money
from app.repository import Repository
from app.schemas import (
    ClientMetrics,
    Confidence,
    Direction,
    Document,
    DocumentType,
    EntityType,
    EvidenceRef,
    GpsPing,
    IncidentType,
    Invoice,
    InvoiceStatus,
    Language,
    Money,
    RiskFactor,
    RiskFactorCode,
    RiskLevel,
    RiskProfile,
    Shipment,
    ShipmentStatus,
    Tone,
)

SCORING_VERSION = "rules-v0"
BASE_SCORE = 30
MIN_PAID_INVOICES = 3  # below this, confidence is low


def _days(a: datetime, b: datetime) -> int:
    return (a.date() - b.date()).days


def _email_responses(repo: Repository, client_id: str) -> list[tuple[float, str, str]]:
    """Return outbound-to-inbound reply times from explicitly linked email threads."""
    threads: dict[str, list] = {}
    for email in repo.emails.list(client_id=client_id):
        if email.thread_id:
            threads.setdefault(email.thread_id, []).append(email)

    responses = []
    for emails in threads.values():
        pending_outbound = None
        for email in sorted(emails, key=lambda item: item.sent_at):
            if email.direction == Direction.outbound:
                pending_outbound = email
            elif email.direction == Direction.inbound and pending_outbound:
                hours = (email.sent_at - pending_outbound.sent_at).total_seconds() / 3600
                if hours >= 0:
                    responses.append((hours, pending_outbound.id, email.id))
                pending_outbound = None
    return responses


def _linked_documents(
    repo: Repository,
    client_id: str,
    *,
    invoices: Sequence[Invoice] = (),
    shipments: Sequence[Shipment] = (),
    email_ids: Sequence[str] = (),
) -> list[Document]:
    """Find documents linked by stored IDs, attachments, or exact extracted references."""
    invoice_number_counts: dict[str, int] = {}
    for invoice in repo.invoices.list():
        invoice_number_counts[invoice.number] = invoice_number_counts.get(invoice.number, 0) + 1
    shipment_reference_counts: dict[str, int] = {}
    for shipment in repo.shipments.list():
        shipment_reference_counts[shipment.reference] = (
            shipment_reference_counts.get(shipment.reference, 0) + 1
        )
    email_document_ids = {
        document_id
        for email in repo.emails.list(client_id=client_id)
        if email.id in email_ids
        for document_id in email.attachment_document_ids
    }
    documents = []
    for document in repo.documents.list():
        if document.client_id not in (None, client_id):
            continue
        if (
            document.id in email_document_ids
            or document.email_id in email_ids
            or any(
                document.invoice_id == invoice.id
                or (
                    document.extracted_fields.get("invoice_number") == invoice.number
                    and invoice_number_counts[invoice.number] == 1
                )
                for invoice in invoices
            )
            or any(
                document.shipment_id == shipment.id
                or (
                    document.extracted_fields.get("shipment_reference") == shipment.reference
                    and shipment_reference_counts[shipment.reference] == 1
                )
                for shipment in shipments
            )
        ):
            documents.append(document)
    return documents


def _emails_for_invoice(repo: Repository, client_id: str, invoice: Invoice) -> list[str]:
    """Find client-linked emails that explicitly mention this invoice number in extracted facts."""
    if len(repo.invoices.list(client_id=client_id, number=invoice.number)) != 1:
        return []
    return [
        email.id
        for email in repo.emails.list(client_id=client_id)
        if (insight := repo.email_insights.get(email.id)) is not None
        and insight.extraction.invoice_number == invoice.number
    ]


def _gps_pings_for_shipment(
    repo: Repository,
    shipment: Shipment,
    now: datetime,
    shipments: Sequence[Shipment],
) -> list[GpsPing]:
    """Use direct shipment links, or a unique truck/time match when Traccar has no shipment ID."""
    related = []
    for ping in repo.gps_pings.list():
        if ping.shipment_id == shipment.id:
            related.append(ping)
            continue
        if shipment.truck_id is None or ping.truck_id != shipment.truck_id:
            continue

        candidates = []
        for candidate in shipments:
            if candidate.truck_id != ping.truck_id:
                continue
            start = candidate.picked_up_at or candidate.pickup_planned_at
            end = candidate.delivered_at or candidate.eta_at or now
            if start <= ping.recorded_at <= end:
                candidates.append(candidate)
        if len(candidates) == 1 and candidates[0].id == shipment.id:
            related.append(ping)
    return related


def _past_due_invoice_documents(
    repo: Repository,
    client_id: str,
    now: datetime,
) -> list[tuple[Document, int]]:
    """Find confidently extracted, linked past-due invoices not already represented as invoices."""
    known_numbers = {invoice.number for invoice in repo.invoices.list(client_id=client_id)}
    latest_by_number: dict[str, Document] = {}
    for document in repo.documents.list(client_id=client_id):
        fields = document.extracted_fields
        number = fields.get("invoice_number")
        if (
            document.doc_type != DocumentType.invoice
            or document.extraction_confidence is None
            or document.extraction_confidence < 0.8
            or not number
            or number in known_numbers
            or not fields.get("due_date")
        ):
            continue
        try:
            due_date = date.fromisoformat(fields["due_date"])
        except ValueError:
            continue
        if due_date >= now.date():
            continue
        previous = latest_by_number.get(number)
        if previous is None or (document.received_at, document.id) > (
            previous.received_at,
            previous.id,
        ):
            latest_by_number[number] = document
    return [
        (document, (now.date() - date.fromisoformat(document.extracted_fields["due_date"])).days)
        for document in latest_by_number.values()
    ]


def compute_profile(client_id: str, repo: Repository, now: datetime) -> RiskProfile:
    client = repo.clients.require(client_id)
    invoices = [i for i in repo.invoices.list(client_id=client_id) if i.status != InvoiceStatus.cancelled]
    payments = repo.payments.list(client_id=client_id)
    shipments = repo.shipments.list(client_id=client_id)
    incidents = repo.incidents.list(client_id=client_id)

    paid_on: dict[str, datetime] = {}
    paid_sum: dict[str, int] = {}
    for p in payments:
        paid_sum[p.invoice_id] = paid_sum.get(p.invoice_id, 0) + p.amount.amount_minor
        paid_on[p.invoice_id] = max(paid_on.get(p.invoice_id, p.paid_at), p.paid_at)

    paid = [i for i in invoices if i.status == InvoiceStatus.paid and i.id in paid_on]
    delays = {i.id: _days(paid_on[i.id], i.due_at) for i in paid}
    overdue = [i for i in invoices if i.status in (InvoiceStatus.issued, InvoiceStatus.partially_paid) and i.due_at < now]
    past_due_documents = _past_due_invoice_documents(repo, client_id, now)
    currency = invoices[0].total.currency if invoices else "EUR"
    overdue_minor = sum(i.total.amount_minor - paid_sum.get(i.id, 0) for i in overdue)
    fines = [x for x in incidents if x.type == IncidentType.fine]

    margin_records = [
        (s, (s.price.amount_minor - s.cost.amount_minor) / s.price.amount_minor * 100)
        for s in shipments
        if s.cost and s.price.amount_minor > 0 and s.price.currency == s.cost.currency
    ]
    margins = [margin for _, margin in margin_records]
    delivered = [s for s in shipments if s.status == ShipmentStatus.delivered and s.delivered_at]
    delayed = [s for s in delivered if (s.delivered_at - s.delivery_planned_at).total_seconds() > 3600]
    email_responses = _email_responses(repo, client_id)

    metrics = ClientMetrics(
        invoices_total=len(invoices),
        invoices_paid=len(paid),
        avg_payment_delay_days=round(sum(delays.values()) / len(delays), 1) if delays else None,
        max_payment_delay_days=max(delays.values()) if delays else None,
        on_time_payment_rate=round(sum(1 for d in delays.values() if d <= 0) / len(delays), 2) if delays else None,
        open_overdue_invoices=len(overdue),
        overdue_amount=Money.of(overdue_minor, currency) if overdue else None,
        max_days_overdue=max(_days(now, i.due_at) for i in overdue) if overdue else None,
        shipments_total=len(shipments),
        delayed_shipments=len(delayed),
        fines_count=len(fines),
        fines_total=Money.of(sum(f.cost.amount_minor for f in fines if f.cost), currency) if fines else None,
        avg_margin_pct=round(sum(margins) / len(margins), 1) if margins else None,
        avg_email_response_hours=round(sum(row[0] for row in email_responses) / len(email_responses), 1)
        if email_responses
        else None,
    )

    factors: list[RiskFactor] = []

    # --- payment behaviour (implemented as the reference example) ---
    if delays:
        late = [i for i in paid if delays[i.id] > 3]
        avg = metrics.avg_payment_delay_days or 0
        if avg > 7:
            invoice_email_ids = {
                invoice.id: _emails_for_invoice(repo, client_id, invoice) for invoice in late
            }
            factors.append(
                RiskFactor(
                    code=RiskFactorCode.late_payment_history,
                    label="Pays late",
                    impact=min(40, int(avg)),
                    explanation=f"Paid {len(late)} of {len(paid)} invoices late, on average {avg:.0f} days after the due date.",
                    evidence=[
                        *[
                            EvidenceRef(
                                entity_type=EntityType.invoice,
                                entity_id=i.id,
                                note=f"{delays[i.id]} days late",
                            )
                            for i in late
                        ],
                        *[
                            EvidenceRef(entity_type=EntityType.document, entity_id=document.id)
                            for document in _linked_documents(
                                repo,
                                client_id,
                                invoices=late,
                                email_ids=[
                                    email_id
                                    for email_ids in invoice_email_ids.values()
                                    for email_id in email_ids
                                ],
                            )
                        ],
                        *[
                            EvidenceRef(entity_type=EntityType.email, entity_id=email_id)
                            for email_ids in invoice_email_ids.values()
                            for email_id in email_ids
                        ],
                    ],
                )
            )
        elif len(paid) >= MIN_PAID_INVOICES and avg <= 2:
            on_time = [i for i in paid if delays[i.id] <= 0]
            invoice_email_ids = {
                invoice.id: _emails_for_invoice(repo, client_id, invoice)
                for invoice in on_time
            }
            factors.append(
                RiskFactor(
                    code=RiskFactorCode.good_payment_history,
                    label="Pays on time",
                    impact=-20,
                    explanation=f"{len(on_time)} of {len(paid)} invoices paid on time (average {avg:+.0f} days vs due date).",
                    evidence=[
                        EvidenceRef(entity_type=EntityType.invoice, entity_id=i.id)
                        for i in on_time
                    ]
                    + [
                        EvidenceRef(entity_type=EntityType.document, entity_id=document.id)
                        for document in _linked_documents(
                            repo,
                            client_id,
                            invoices=on_time,
                            email_ids=[
                                email_id
                                for email_ids in invoice_email_ids.values()
                                for email_id in email_ids
                            ],
                        )
                    ]
                    + [
                        EvidenceRef(entity_type=EntityType.email, entity_id=email_id)
                        for email_ids in invoice_email_ids.values()
                        for email_id in email_ids
                    ],
                )
            )
    if overdue or past_due_documents:
        worst = max(
            [
                *(_days(now, invoice.due_at) for invoice in overdue),
                *(days for _, days in past_due_documents),
            ]
        )
        invoice_email_ids = {invoice.id: _emails_for_invoice(repo, client_id, invoice) for invoice in overdue}
        document_amounts: dict[str, int] = {}
        for document, _ in past_due_documents:
            fields = document.extracted_fields
            amount = fields.get("total_amount")
            currency_code = fields.get("currency", "EUR").upper()
            if (
                not amount
                or len(currency_code) != 3
                or not currency_code.isascii()
                or not currency_code.isalpha()
            ):
                continue
            try:
                amount_minor = int((Decimal(amount) * 100).quantize(Decimal(1)))
            except (InvalidOperation, ValueError):
                continue
            document_amounts[currency_code] = document_amounts.get(currency_code, 0) + amount_minor
        document_amount_text = ", ".join(
            format_money(Money.of(amount, currency_code), Language.en)
            for currency_code, amount in sorted(document_amounts.items())
        )
        verified_overdue = (
            f"{len(overdue)} unpaid invoice(s) past due, "
            f"{format_money(metrics.overdue_amount, Language.en)} in total; "
            if overdue
            else ""
        )
        unverified_documents = (
            f"{len(past_due_documents)} linked invoice PDF(s) show a past-due date"
            f"{f' and total {document_amount_text}' if document_amount_text else ''}; "
            "payment status is not recorded for those documents; "
            if past_due_documents
            else ""
        )
        factors.append(
            RiskFactor(
                code=RiskFactorCode.currently_overdue,
                label="Has overdue invoices",
                impact=min(30, 10 + worst // 3) if overdue else min(20, 5 + worst // 7),
                explanation=(
                    f"{verified_overdue}{unverified_documents}oldest due date was {worst} days ago."
                ),
                evidence=[
                    *[
                        EvidenceRef(
                            entity_type=EntityType.invoice,
                            entity_id=i.id,
                            note=f"due {i.due_at.date()}",
                        )
                        for i in overdue
                    ],
                    *[
                        EvidenceRef(entity_type=EntityType.document, entity_id=document.id)
                        for document in _linked_documents(
                            repo,
                            client_id,
                            invoices=overdue,
                            email_ids=[
                                email_id for email_ids in invoice_email_ids.values() for email_id in email_ids
                            ],
                        )
                    ],
                    *[
                        EvidenceRef(entity_type=EntityType.email, entity_id=email_id)
                        for email_ids in invoice_email_ids.values()
                        for email_id in email_ids
                    ],
                    *[
                        EvidenceRef(entity_type=EntityType.document, entity_id=document.id)
                        for document, _ in past_due_documents
                    ],
                ],
            )
        )
    if fines:
        factors.append(
            RiskFactor(
                code=RiskFactorCode.fines_history,
                label="Fines us for delays",
                impact=min(25, 10 * len(fines)),
                explanation=f"Charged us {len(fines)} penalt{'y' if len(fines) == 1 else 'ies'} ({format_money(metrics.fines_total, Language.en)}) — strict on delivery slots.",
                evidence=[EvidenceRef(entity_type=EntityType.incident, entity_id=f.id) for f in fines],
            )
        )
    delay_incidents = [i for i in incidents if i.type == IncidentType.delay]
    fined_shipment_ids = {i.shipment_id for i in fines if i.shipment_id}
    client_emails = repo.emails.list(client_id=client_id)
    delay_emails = [
        email
        for email in client_emails
        if email.direction == Direction.inbound
        and (
            {"penalty", "complaint"}.intersection(label.lower() for label in email.labels)
            or (
                (insight := repo.email_insights.get(email.id)) is not None
                and insight.extraction.intent.value in {"complaint", "delay_inquiry"}
            )
        )
        and (not email.shipment_id or email.shipment_id not in fined_shipment_ids)
    ]
    if delay_incidents or delay_emails:
        delay_shipment_ids = {
            shipment_id
            for shipment_id in (
                *(incident.shipment_id for incident in delay_incidents),
                *(email.shipment_id for email in delay_emails),
            )
            if shipment_id
        }
        delay_shipments = [shipment for shipment in shipments if shipment.id in delay_shipment_ids]
        delay_documents = _linked_documents(
            repo,
            client_id,
            shipments=delay_shipments,
            email_ids=[email.id for email in delay_emails],
        )
        delay_pings = [
            ping
            for shipment in delay_shipments
            for ping in _gps_pings_for_shipment(repo, shipment, now, shipments)
        ]
        factors.append(
            RiskFactor(
                code=RiskFactorCode.delay_sensitivity,
                label="Sensitive to delivery delays",
                impact=min(25, 8 * (len(delay_incidents) + len(delay_emails))),
                explanation=(
                    f"Recorded {len(delay_incidents)} delay incident(s) and "
                    f"{len(delay_emails)} additional penalty/complaint email(s) about delivery timing."
                ),
                evidence=[
                    *[
                        EvidenceRef(entity_type=EntityType.incident, entity_id=i.id)
                        for i in delay_incidents
                    ],
                    *[
                        EvidenceRef(entity_type=EntityType.email, entity_id=email.id)
                        for email in delay_emails
                    ],
                    *[
                        EvidenceRef(entity_type=EntityType.shipment, entity_id=shipment.id)
                        for shipment in delay_shipments
                    ],
                    *[
                        EvidenceRef(entity_type=EntityType.document, entity_id=document.id)
                        for document in delay_documents
                    ],
                    *[
                        EvidenceRef(entity_type=EntityType.gps_ping, entity_id=ping.id)
                        for ping in delay_pings
                    ],
                ],
            )
        )
    damage_claims = [i for i in incidents if i.type in (IncidentType.damage, IncidentType.claim)]
    if damage_claims:
        claim_shipments = [
            shipment for shipment in shipments if any(i.shipment_id == shipment.id for i in damage_claims)
        ]
        documented_costs: dict[str, int] = {}
        for incident in damage_claims:
            if incident.cost:
                documented_costs[incident.cost.currency] = (
                    documented_costs.get(incident.cost.currency, 0) + incident.cost.amount_minor
                )
        cost_text = ", ".join(
            format_money(Money.of(amount, currency), Language.en)
            for currency, amount in sorted(documented_costs.items())
        ) or "no documented costs"
        factors.append(
            RiskFactor(
                code=RiskFactorCode.damage_claims,
                label="Damage or cargo claims",
                impact=min(30, 15 * len(damage_claims)),
                explanation=(
                    f"Recorded {len(damage_claims)} damage/claim incident(s); "
                    f"{sum(i.cost is not None for i in damage_claims)} have documented costs totaling {cost_text}."
                ),
                evidence=[
                    EvidenceRef(entity_type=EntityType.incident, entity_id=i.id)
                    for i in damage_claims
                ]
                + [
                    EvidenceRef(entity_type=EntityType.document, entity_id=document.id)
                    for document in _linked_documents(repo, client_id, shipments=claim_shipments)
                ],
            )
        )
    if margin_records and metrics.avg_margin_pct is not None and metrics.avg_margin_pct < 12:
        low_margin_records = [(shipment, margin) for shipment, margin in margin_records if margin < 12]
        lane_margins: dict[tuple[str, str], list[float]] = {}
        for shipment, margin in margin_records:
            lane = (shipment.origin.city, shipment.destination.city)
            lane_margins.setdefault(lane, []).append(margin)
        worst_lane, worst_lane_margins = min(
            lane_margins.items(), key=lambda item: sum(item[1]) / len(item[1])
        )
        avg_margin = metrics.avg_margin_pct
        impact = min(25, max(5, round((12 - avg_margin) * 2)))
        factors.append(
            RiskFactor(
                code=RiskFactorCode.low_margin,
                label="Low shipment margins",
                impact=impact,
                explanation=(
                    f"Average margin was {avg_margin:.1f}% across {len(margin_records)} shipment(s), below 12%; "
                    f"thinnest lane {worst_lane[0]} → {worst_lane[1]} averaged "
                    f"{sum(worst_lane_margins) / len(worst_lane_margins):.1f}% "
                    f"across {len(worst_lane_margins)} shipment(s)."
                ),
                evidence=[
                    EvidenceRef(
                        entity_type=EntityType.shipment,
                        entity_id=shipment.id,
                        note=f"{margin:.1f}% margin",
                    )
                    for shipment, margin in low_margin_records
                ],
            )
        )
    restricted_shipments = []
    for shipment in shipments:
        outside_accepted = (
            bool(client.accepted_cargo_types)
            and shipment.cargo_type not in client.accepted_cargo_types
        )
        if (
            shipment.cargo_type in client.refused_cargo_types
            or outside_accepted
        ):
            restricted_shipments.append(shipment)
    if restricted_shipments:
        conflict_counts: dict[str, int] = {}
        for shipment in restricted_shipments:
            conflict_counts[shipment.cargo_type.value] = conflict_counts.get(shipment.cargo_type.value, 0) + 1
        conflict_text = ", ".join(
            f"{cargo_type}: {count}" for cargo_type, count in sorted(conflict_counts.items())
        )
        factors.append(
            RiskFactor(
                code=RiskFactorCode.cargo_restrictions,
                label="Cargo restrictions conflict with shipments",
                impact=min(20, 8 * len(restricted_shipments)),
                explanation=(
                    f"{len(restricted_shipments)} of {len(shipments)} shipment(s) conflicted with the client's "
                    f"accepted/refused cargo list ({conflict_text})."
                ),
                evidence=[
                    EvidenceRef(entity_type=EntityType.shipment, entity_id=s.id)
                    for s in restricted_shipments
                ],
            )
        )
    if email_responses and metrics.avg_email_response_hours is not None and metrics.avg_email_response_hours >= 48:
        factors.append(
            RiskFactor(
                code=RiskFactorCode.slow_communication,
                label="Slow email responses",
                impact=min(20, max(5, int(metrics.avg_email_response_hours // 24) * 2)),
                explanation=(
                    f"Across {len(email_responses)} tracked reply/replies, email response averaged "
                    f"{metrics.avg_email_response_hours:.1f} hours (48-hour threshold)."
                ),
                evidence=[
                    ref
                    for _, outbound_id, inbound_id in email_responses
                    for ref in (
                        EvidenceRef(entity_type=EntityType.email, entity_id=outbound_id),
                        EvidenceRef(entity_type=EntityType.email, entity_id=inbound_id),
                    )
                ],
            )
        )
    if len(paid) < MIN_PAID_INVOICES:
        factors.append(
            RiskFactor(
                code=RiskFactorCode.insufficient_history,
                label="Little history",
                impact=10,
                explanation=f"Only {len(paid)} paid invoice(s) on record; score is a rough estimate.",
                evidence=[
                    EvidenceRef(
                        entity_type=EntityType.client,
                        entity_id=client_id,
                        note=f"{len(paid)} paid invoice(s) recorded",
                    )
                ],
            )
        )

    factors.sort(key=lambda f: abs(f.impact), reverse=True)
    score = max(0, min(100, BASE_SCORE + sum(f.impact for f in factors)))
    level = RiskLevel.unknown if not invoices and not past_due_documents else RiskLevel.high if score >= 65 else RiskLevel.medium if score >= 40 else RiskLevel.low
    confidence = Confidence.low if len(paid) < MIN_PAID_INVOICES else Confidence.high if len(paid) >= 8 else Confidence.medium
    codes = {f.code for f in factors}
    tone = (
        Tone.firm
        if {RiskFactorCode.currently_overdue, RiskFactorCode.late_payment_history} <= codes
        else Tone.formal
        if RiskFactorCode.fines_history in codes
        else Tone.friendly
    )
    summary = "; ".join(f.label for f in factors[:3]) or "No notable risk signals."

    return RiskProfile(
        client_id=client_id,
        computed_at=now,
        score=score,
        level=level,
        confidence=confidence,
        factors=factors,
        metrics=metrics,
        observed_cargo_types=sorted({s.cargo_type for s in shipments}),
        recommended_tone=tone,
        summary=summary,
        scoring_version=SCORING_VERSION,
    )


def get_profile(client_id: str, repo: Repository, now: datetime) -> RiskProfile:
    """Public entry point for other modules (drafting uses this). Recomputes (cheap) and stores the result."""
    return repo.risk_profiles.upsert(compute_profile(client_id, repo, now))
