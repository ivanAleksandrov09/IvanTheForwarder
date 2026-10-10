"""Canonical enum values: lowercase snake_case, one list per concept.
Adding/renaming a value is a schema change -> see CONVENTIONS.md "How to change a schema". Owner: lead.
"""

from enum import StrEnum


class Language(StrEnum):  # ISO 639-1
    bg = "bg"
    en = "en"
    ru = "ru"
    tr = "tr"
    ro = "ro"


class SourceType(StrEnum):
    """Where data came from. One active connector per source."""

    email = "email"
    documents = "documents"
    gps = "gps"
    erp = "erp"
    call_log = "call_log"  # stretch
    erp_screenshot = "erp_screenshot"  # stretch (vision/OCR)
    external_web = "external_web"  # stretch (web search, speditor.net)
    manual = "manual"


class PayloadType(StrEnum):
    client = "client"
    truck = "truck"
    gps_ping = "gps_ping"
    shipment = "shipment"
    email = "email"
    document = "document"
    invoice = "invoice"
    payment = "payment"
    incident = "incident"
    call_log = "call_log"


class EntityType(StrEnum):
    """Used in EvidenceRef to point at any stored object."""

    client = "client"
    truck = "truck"
    gps_ping = "gps_ping"
    shipment = "shipment"
    email = "email"
    document = "document"
    invoice = "invoice"
    payment = "payment"
    incident = "incident"
    call_log = "call_log"
    event = "event"
    draft = "draft"


class ShipmentStatus(StrEnum):
    quoted = "quoted"
    booked = "booked"
    in_transit = "in_transit"
    delivered = "delivered"
    cancelled = "cancelled"


class CargoType(StrEnum):
    general = "general"
    palletized = "palletized"
    refrigerated = "refrigerated"
    pharma = "pharma"
    adr_dangerous = "adr_dangerous"
    oversized = "oversized"
    bulk = "bulk"
    food = "food"
    textile = "textile"
    steel = "steel"
    grain = "grain"
    furniture = "furniture"
    automotive = "automotive"


class TrailerType(StrEnum):
    tent = "tent"
    mega = "mega"
    reefer = "reefer"
    flatbed = "flatbed"
    tanker = "tanker"
    box = "box"


class TruckStatus(StrEnum):
    available = "available"
    loading = "loading"
    en_route = "en_route"
    unloading = "unloading"
    maintenance = "maintenance"


class Direction(StrEnum):
    inbound = "inbound"
    outbound = "outbound"


class DocumentType(StrEnum):
    cmr = "cmr"
    invoice = "invoice"
    rate_sheet = "rate_sheet"
    transport_order = "transport_order"
    pod = "pod"  # proof of delivery
    customs = "customs"
    other = "other"


class InvoiceStatus(StrEnum):
    """Payment state only. "Overdue" is NOT a status: it is derived from due_at vs clock.now()."""

    draft = "draft"
    issued = "issued"
    partially_paid = "partially_paid"
    paid = "paid"
    cancelled = "cancelled"


class PaymentMethod(StrEnum):
    bank_transfer = "bank_transfer"
    cash = "cash"
    card = "card"
    offset = "offset"


class IncidentType(StrEnum):
    delay = "delay"
    fine = "fine"  # penalty charged to us by the client
    damage = "damage"
    claim = "claim"
    documentation_error = "documentation_error"
    cancellation = "cancellation"


class Severity(StrEnum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class RiskLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    unknown = "unknown"  # not enough history


class Confidence(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class RiskFactorCode(StrEnum):
    late_payment_history = "late_payment_history"
    currently_overdue = "currently_overdue"
    good_payment_history = "good_payment_history"
    delay_sensitivity = "delay_sensitivity"
    fines_history = "fines_history"
    damage_claims = "damage_claims"
    low_margin = "low_margin"
    slow_communication = "slow_communication"
    cargo_restrictions = "cargo_restrictions"
    insufficient_history = "insufficient_history"


class EventType(StrEnum):
    shipment_delayed = "shipment_delayed"
    invoice_overdue = "invoice_overdue"
    payment_received = "payment_received"
    email_received = "email_received"
    document_received = "document_received"
    risk_level_changed = "risk_level_changed"
    truck_idle = "truck_idle"


class DraftKind(StrEnum):
    payment_reminder = "payment_reminder"
    delay_notice = "delay_notice"
    quote_reply = "quote_reply"
    invoice = "invoice"
    cmr = "cmr"
    generic = "generic"


class DraftChannel(StrEnum):
    email = "email"
    sms = "sms"
    viber = "viber"
    document = "document"


class DraftStatus(StrEnum):
    """pending_review -> approved -> sent | failed ; pending_review -> rejected. Only `approved` can be sent."""

    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"
    sent = "sent"
    failed = "failed"


class Tone(StrEnum):
    formal = "formal"
    friendly = "friendly"
    firm = "firm"
    apologetic = "apologetic"


class LlmMode(StrEnum):
    mock = "mock"
    live = "live"


class ConnectorHealth(StrEnum):
    ok = "ok"
    degraded = "degraded"
    down = "down"
    disabled = "disabled"
