"""Detect things worth acting on. Owner: B.

Every detector is pure: (repo, now) -> list[DomainEvent]. IDs are stable_id(type, entity) so re-running
detection updates existing events instead of duplicating them.
"""

from datetime import datetime

from app.core.ids import stable_id
from app.repository import Repository
from app.schemas import (
    DomainEvent,
    EntityType,
    EventType,
    EvidenceRef,
    InvoiceStatus,
    Severity,
    ShipmentStatus,
)

OVERDUE_MIN_DAYS = 7
DELAY_MIN_MINUTES = 60


def detect_overdue_invoices(repo: Repository, now: datetime) -> list[DomainEvent]:
    events = []
    for inv in repo.invoices.list(where=lambda i: i.status in (InvoiceStatus.issued, InvoiceStatus.partially_paid)):
        days = (now.date() - inv.due_at.date()).days
        if days < OVERDUE_MIN_DAYS:
            continue
        client = repo.clients.get(inv.client_id)
        severity = Severity.high if days >= 30 else Severity.medium
        events.append(
            DomainEvent(
                id=stable_id("evt", EventType.invoice_overdue, inv.id),
                type=EventType.invoice_overdue,
                severity=severity,
                occurred_at=inv.due_at,
                detected_at=now,
                client_id=inv.client_id,
                invoice_id=inv.id,
                title=f"Invoice {inv.number} is {days} days overdue",
                description=f"{client.name if client else inv.client_id}: invoice {inv.number} was due {inv.due_at.date()}, still unpaid.",
                data={"days_overdue": days, "amount_minor": inv.total.amount_minor, "currency": inv.total.currency},
                evidence=[EvidenceRef(entity_type=EntityType.invoice, entity_id=inv.id)],
            )
        )
    return events


def detect_shipment_delays(repo: Repository, now: datetime) -> list[DomainEvent]:
    """Uses Shipment.eta_at vs delivery_planned_at.
    TODO(owner B): compute/refresh eta_at from GPS pings (remaining distance / avg speed + mandatory rest),
                   and fill data["reason"] (e.g. stationary > 60 min near a known border crossing).
    """
    events = []
    for s in repo.shipments.list(status=ShipmentStatus.in_transit):
        if s.eta_at is None:
            continue
        delay_min = int((s.eta_at - s.delivery_planned_at).total_seconds() // 60)
        if delay_min < DELAY_MIN_MINUTES:
            continue
        events.append(
            DomainEvent(
                id=stable_id("evt", EventType.shipment_delayed, s.id),
                type=EventType.shipment_delayed,
                severity=Severity.high if delay_min >= 120 else Severity.medium,
                occurred_at=now,
                detected_at=now,
                client_id=s.client_id,
                shipment_id=s.id,
                truck_id=s.truck_id,
                title=f"Shipment {s.reference} projected {delay_min // 60}h{delay_min % 60:02d}m late",
                description=f"{s.origin.city} → {s.destination.city}: ETA {s.eta_at:%Y-%m-%d %H:%M}Z vs slot {s.delivery_planned_at:%Y-%m-%d %H:%M}Z.",
                data={"delay_minutes": delay_min, "reason": None},
                evidence=[EvidenceRef(entity_type=EntityType.shipment, entity_id=s.id)],
            )
        )
    return events


DETECTORS = [detect_overdue_invoices, detect_shipment_delays]
# TODO(owner B): payment_received, truck_idle, risk_level_changed, email_received (urgent/complaint)


def run_detectors(repo: Repository, now: datetime) -> tuple[list[DomainEvent], list[DomainEvent]]:
    """Returns (all_current_events, newly_created_events). Preserves handled/draft_ids on re-detection."""
    current, new = [], []
    for detector in DETECTORS:
        for ev in detector(repo, now):
            existing = repo.events.get(ev.id)
            if existing:
                ev = ev.model_copy(update={"handled": existing.handled, "draft_ids": existing.draft_ids})
            else:
                new.append(ev)
            current.append(repo.events.upsert(ev))
    return current, new
