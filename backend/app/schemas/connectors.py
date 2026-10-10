"""Connector output contract. Every connector returns list[ConnectorEnvelope]; nothing else."""

from pydantic import model_validator

from app.schemas.common import SCHEMA_VERSION, ContractModel, EnvelopeId, UtcDatetime
from app.schemas.entities import (
    CallLog,
    Client,
    Document,
    Email,
    GpsPing,
    Incident,
    Invoice,
    Payment,
    Shipment,
    Truck,
)
from app.schemas.enums import ConnectorHealth, PayloadType, SourceType

PAYLOAD_MODELS: dict[PayloadType, type[ContractModel]] = {
    PayloadType.client: Client,
    PayloadType.truck: Truck,
    PayloadType.gps_ping: GpsPing,
    PayloadType.shipment: Shipment,
    PayloadType.email: Email,
    PayloadType.document: Document,
    PayloadType.invoice: Invoice,
    PayloadType.payment: Payment,
    PayloadType.incident: Incident,
    PayloadType.call_log: CallLog,
}


class ConnectorEnvelope(ContractModel):
    """Versioned wrapper around one object produced by a connector (a.k.a. ConnectorEvent)."""

    envelope_id: EnvelopeId
    schema_version: str = SCHEMA_VERSION
    source: SourceType
    connector: str  # implementation name, e.g. "email.mock", "email.imap"
    fetched_at: UtcDatetime
    external_id: str | None = None  # ID in the source system (Message-ID, ERP row id) for dedupe
    payload_type: PayloadType
    payload: Client | Truck | GpsPing | Shipment | Email | Document | Invoice | Payment | Incident | CallLog

    @model_validator(mode="after")
    def _payload_matches_type(self):
        expected = PAYLOAD_MODELS[self.payload_type]
        if not isinstance(self.payload, expected):
            raise ValueError(f"payload is {type(self.payload).__name__}, expected {expected.__name__}")
        return self


class ConnectorInfo(ContractModel):
    source: SourceType
    connector: str
    mode: str  # "mock" | "live"
    health: ConnectorHealth
    description: str
    last_sync_at: UtcDatetime | None = None
    last_error: str | None = None


class SyncResult(ContractModel):
    source: SourceType
    connector: str
    fetched: int
    upserted: int
    errors: list[str] = []
    started_at: UtcDatetime
    finished_at: UtcDatetime
