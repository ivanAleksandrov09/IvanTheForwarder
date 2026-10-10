"""Business entities (what connectors produce and the repository stores). Owner: lead."""

from typing import Annotated

from pydantic import Field, StringConstraints, model_validator

from app.schemas.common import (
    CallLogId,
    ClientId,
    ContractModel,
    CountryCode,
    DocumentId,
    EmailAddress,
    EmailId,
    GpsPingId,
    IncidentId,
    InvoiceId,
    Location,
    Money,
    PaymentId,
    PhoneE164,
    Ratio,
    ShipmentId,
    TruckId,
    UtcDatetime,
)
from app.schemas.enums import (
    CargoType,
    Direction,
    DocumentType,
    IncidentType,
    InvoiceStatus,
    Language,
    PaymentMethod,
    Severity,
    ShipmentStatus,
    SourceType,
    TrailerType,
    TruckStatus,
)


class Contact(ContractModel):
    name: str  # original script, no transliteration
    role: str | None = None
    email: EmailAddress | None = None
    phone: PhoneE164 | None = None
    language: Language


class Client(ContractModel):
    id: ClientId
    name: str  # legal name in original script, e.g. "Балкан Стил ООД"
    name_latin: str | None = None  # only if the client itself uses one; never auto-transliterated
    vat_number: str | None = None  # e.g. "BG204512378"
    country: CountryCode
    city: str
    preferred_language: Language
    contacts: list[Contact] = []
    payment_terms_days: int = Field(ge=0)
    credit_limit: Money | None = None
    accepted_cargo_types: list[CargoType] = []  # declared in contract/emails
    refused_cargo_types: list[CargoType] = []
    notes: str | None = None  # internal; NEVER copied into outgoing messages
    created_at: UtcDatetime


class Truck(ContractModel):
    id: TruckId
    plate_number: str  # as registered, Bulgarian plates in Cyrillic e.g. "СВ 1234 АВ"
    label: str  # dispatcher nickname, e.g. "Truck 3"
    driver_name: str | None = None
    driver_phone: PhoneE164 | None = None
    trailer_type: TrailerType
    capacity_kg: int = Field(ge=0)
    status: TruckStatus
    is_own_fleet: bool  # false = subcontracted carrier
    current_shipment_id: ShipmentId | None = None


class GpsPing(ContractModel):
    id: GpsPingId
    truck_id: TruckId
    shipment_id: ShipmentId | None = None
    recorded_at: UtcDatetime
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    speed_kmh: float = Field(ge=0)
    heading_deg: float | None = Field(default=None, ge=0, lt=360)


class Shipment(ContractModel):
    id: ShipmentId
    reference: str  # internal order ref, e.g. "SPD-2026-0901"
    client_id: ClientId
    truck_id: TruckId | None = None
    status: ShipmentStatus
    cargo_type: CargoType
    cargo_description: str
    weight_kg: int = Field(ge=0)
    pallets: int | None = Field(default=None, ge=0)
    origin: Location
    destination: Location
    distance_km: float = Field(ge=0)
    pickup_planned_at: UtcDatetime
    delivery_planned_at: UtcDatetime  # the slot promised to the client
    picked_up_at: UtcDatetime | None = None
    delivered_at: UtcDatetime | None = None
    eta_at: UtcDatetime | None = None  # latest estimate (telematics or our projection)
    price: Money  # charged to client
    cost: Money | None = None  # our cost (carrier, fuel, tolls) -> margin
    cmr_number: str | None = None
    created_at: UtcDatetime


class Email(ContractModel):
    id: EmailId
    message_id: str | None = None  # RFC 5322 Message-ID from the source (idempotency key)
    thread_id: str | None = None
    mailbox: str  # e.g. "office@vitosha-spedition.bg"
    direction: Direction
    from_address: EmailAddress
    from_name: str | None = None
    to_addresses: list[EmailAddress]
    cc_addresses: list[EmailAddress] = []
    subject: str
    body_text: str
    language: Language | None = None  # detected; null if unknown
    sent_at: UtcDatetime
    client_id: ClientId | None = None  # linked by connector/ingest
    shipment_id: ShipmentId | None = None
    attachment_document_ids: list[DocumentId] = []
    labels: list[str] = []


class Document(ContractModel):
    id: DocumentId
    doc_type: DocumentType
    filename: str
    mime_type: str
    source: SourceType
    received_at: UtcDatetime
    language: Language | None = None
    client_id: ClientId | None = None
    shipment_id: ShipmentId | None = None
    invoice_id: InvoiceId | None = None
    email_id: EmailId | None = None
    extracted_text: str | None = None
    # Flat key -> string. Allowed keys per doc_type are listed in CONVENTIONS.md (e.g. cmr_number, gross_weight_kg).
    extracted_fields: dict[str, str] = {}
    extraction_confidence: Ratio | None = None


InvoiceNumber = Annotated[str, StringConstraints(pattern=r"^[0-9]{10}$")]  # Bulgarian invoices: 10 digits


class Invoice(ContractModel):
    id: InvoiceId
    number: InvoiceNumber
    client_id: ClientId
    shipment_ids: list[ShipmentId] = []
    issued_at: UtcDatetime
    due_at: UtcDatetime
    net: Money
    vat: Money
    total: Money
    status: InvoiceStatus

    @model_validator(mode="after")
    def _check_amounts(self):
        if not (self.net.currency == self.vat.currency == self.total.currency):
            raise ValueError("net, vat and total must use the same currency")
        if self.net.amount_minor + self.vat.amount_minor != self.total.amount_minor:
            raise ValueError("total must equal net + vat")
        if self.due_at < self.issued_at:
            raise ValueError("due_at must not be before issued_at")
        return self


class Payment(ContractModel):
    id: PaymentId
    invoice_id: InvoiceId
    client_id: ClientId
    amount: Money
    paid_at: UtcDatetime
    method: PaymentMethod
    reference: str | None = None  # bank transfer reference


class Incident(ContractModel):
    id: IncidentId
    type: IncidentType
    severity: Severity
    occurred_at: UtcDatetime
    client_id: ClientId | None = None
    shipment_id: ShipmentId | None = None
    truck_id: TruckId | None = None
    description: str
    delay_minutes: int | None = Field(default=None, ge=0)
    cost: Money | None = None  # fine/claim amount charged to us


class CallLog(ContractModel):  # stretch
    id: CallLogId
    direction: Direction
    from_number: PhoneE164
    to_number: PhoneE164
    started_at: UtcDatetime
    duration_seconds: int = Field(ge=0)
    client_id: ClientId | None = None
    language: Language | None = None
    summary: str | None = None
    transcript: str | None = None
