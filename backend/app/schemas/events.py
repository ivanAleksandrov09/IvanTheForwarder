"""Domain events: things the assistant noticed and may act on (proactive layer)."""

from app.schemas.common import (
    ClientId,
    ContractModel,
    DraftId,
    EventId,
    EvidenceRef,
    InvoiceId,
    ShipmentId,
    TruckId,
    UtcDatetime,
)
from app.schemas.enums import EventType, Severity


class DomainEvent(ContractModel):
    id: EventId  # stable_id("evt", type, entity_id) -> re-detection is idempotent
    type: EventType
    severity: Severity
    occurred_at: UtcDatetime
    detected_at: UtcDatetime
    client_id: ClientId | None = None
    shipment_id: ShipmentId | None = None
    truck_id: TruckId | None = None
    invoice_id: InvoiceId | None = None
    title: str  # short, for the UI
    description: str  # facts with numbers
    # Display-only facts (e.g. {"delay_minutes": 140}). Logic must NOT depend on keys here; add real fields instead.
    data: dict[str, str | int | float | bool | None] = {}
    evidence: list[EvidenceRef] = []
    handled: bool = False
    draft_ids: list[DraftId] = []
