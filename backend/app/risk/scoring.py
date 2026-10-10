"""Explainable client risk scoring. Owner: B.

score = BASE + sum(factor.impact), clamped to 0..100. Each factor carries a sentence with the numbers
and EvidenceRefs to the invoices/incidents that produced it. No black-box numbers.
"""

from datetime import datetime

from app.core.formatting import format_money
from app.repository import Repository
from app.schemas import (
    ClientMetrics,
    Confidence,
    EntityType,
    EvidenceRef,
    IncidentType,
    InvoiceStatus,
    Language,
    Money,
    RiskFactor,
    RiskFactorCode,
    RiskLevel,
    RiskProfile,
    ShipmentStatus,
    Tone,
)

SCORING_VERSION = "rules-v0"
BASE_SCORE = 30
MIN_PAID_INVOICES = 3  # below this, confidence is low


def _days(a: datetime, b: datetime) -> int:
    return (a.date() - b.date()).days


def compute_profile(client_id: str, repo: Repository, now: datetime) -> RiskProfile:
    repo.clients.require(client_id)
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
    currency = invoices[0].total.currency if invoices else "EUR"
    overdue_minor = sum(i.total.amount_minor - paid_sum.get(i.id, 0) for i in overdue)
    fines = [x for x in incidents if x.type == IncidentType.fine]

    margins = [
        (s.price.amount_minor - s.cost.amount_minor) / s.price.amount_minor * 100
        for s in shipments
        if s.cost and s.price.amount_minor > 0
    ]
    delivered = [s for s in shipments if s.status == ShipmentStatus.delivered and s.delivered_at]
    delayed = [s for s in delivered if (s.delivered_at - s.delivery_planned_at).total_seconds() > 3600]

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
        avg_email_response_hours=None,  # TODO(owner B): from email threads (inbound -> our reply / their reply)
    )

    factors: list[RiskFactor] = []

    # --- payment behaviour (implemented as the reference example) ---
    if delays:
        late = [i for i in paid if delays[i.id] > 3]
        avg = metrics.avg_payment_delay_days or 0
        if avg > 7:
            factors.append(
                RiskFactor(
                    code=RiskFactorCode.late_payment_history,
                    label="Pays late",
                    impact=min(40, int(avg)),
                    explanation=f"Paid {len(late)} of {len(paid)} invoices late, on average {avg:.0f} days after the due date.",
                    evidence=[EvidenceRef(entity_type=EntityType.invoice, entity_id=i.id, note=f"{delays[i.id]} days late") for i in late[:5]],
                )
            )
        elif len(paid) >= MIN_PAID_INVOICES and avg <= 2:
            factors.append(
                RiskFactor(
                    code=RiskFactorCode.good_payment_history,
                    label="Pays on time",
                    impact=-20,
                    explanation=f"{len(paid) - len(late)} of {len(paid)} invoices paid on time (average {avg:+.0f} days vs due date).",
                )
            )
    if overdue:
        worst = max(_days(now, i.due_at) for i in overdue)
        factors.append(
            RiskFactor(
                code=RiskFactorCode.currently_overdue,
                label="Has overdue invoices",
                impact=min(30, 10 + worst // 3),
                explanation=f"{len(overdue)} unpaid invoice(s) past due, {format_money(metrics.overdue_amount, Language.en)} in total; oldest {worst} days overdue.",
                evidence=[EvidenceRef(entity_type=EntityType.invoice, entity_id=i.id, note=f"due {i.due_at.date()}") for i in overdue],
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
    if len(paid) < MIN_PAID_INVOICES:
        factors.append(
            RiskFactor(
                code=RiskFactorCode.insufficient_history,
                label="Little history",
                impact=10,
                explanation=f"Only {len(paid)} paid invoice(s) on record; score is a rough estimate.",
            )
        )
    # TODO(owner B): delay_sensitivity  (client complaints in emails, tight slots, incidents of type delay)
    # TODO(owner B): low_margin         (avg_margin_pct below company threshold, per route)
    # TODO(owner B): slow_communication (avg_email_response_hours)
    # TODO(owner B): cargo_restrictions (refused_cargo_types vs requested cargo; observed vs declared)
    # TODO(owner B): damage_claims      (incidents of type damage/claim)

    factors.sort(key=lambda f: abs(f.impact), reverse=True)
    score = max(0, min(100, BASE_SCORE + sum(f.impact for f in factors)))
    level = RiskLevel.unknown if not invoices else RiskLevel.high if score >= 65 else RiskLevel.medium if score >= 40 else RiskLevel.low
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
