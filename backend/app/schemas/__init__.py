"""THE single source of truth for every data shape in the project.

- Backend code imports models from here (`from app.schemas import Client`), never redefines them.
- Frontend types are GENERATED from these via OpenAPI (`npm run gen:types`), never hand-written.
- Changes: lead only, small PR, announce in team chat (see CONVENTIONS.md).
"""

from app.schemas.api import HealthResponse, LlmPingRequest, LlmPingResponse, LlmStatus, ResetResponse
from app.schemas.common import (
    SCHEMA_VERSION,
    ContractModel,
    EvidenceRef,
    Location,
    Money,
    UtcDatetime,
)
from app.schemas.connectors import PAYLOAD_MODELS, ConnectorEnvelope, ConnectorInfo, SyncResult
from app.schemas.drafts import (
    ApproveDraftRequest,
    DraftContent,
    DraftMessage,
    GenerateDraftRequest,
    LlmMeta,
    RejectDraftRequest,
    SendResult,
    UpdateDraftRequest,
)
from app.schemas.entities import (
    CallLog,
    Client,
    Contact,
    Document,
    Email,
    GpsPing,
    Incident,
    Invoice,
    Payment,
    Shipment,
    Truck,
)
from app.schemas.enums import *  # noqa: F401,F403  (re-export every enum)
from app.schemas.enums import PayloadType
from app.schemas.events import DomainEvent
from app.schemas.mailbox import EmailExtraction, EmailInsight, LinkEmailRequest, MailboxLoginRequest, MailboxStatus
from app.schemas.risk import ClientMetrics, RiskFactor, RiskProfile

# collection name -> (model, primary key field). Used by repository, seed generator and validation tests.
COLLECTIONS: dict[str, tuple[type[ContractModel], str]] = {
    "clients": (Client, "id"),
    "trucks": (Truck, "id"),
    "gps_pings": (GpsPing, "id"),
    "shipments": (Shipment, "id"),
    "emails": (Email, "id"),
    "documents": (Document, "id"),
    "invoices": (Invoice, "id"),
    "payments": (Payment, "id"),
    "incidents": (Incident, "id"),
    "call_logs": (CallLog, "id"),
    "events": (DomainEvent, "id"),
    "drafts": (DraftMessage, "id"),
    "risk_profiles": (RiskProfile, "client_id"),
    "email_insights": (EmailInsight, "email_id"),
}

# Collections shipped as seed files in data/seed/<name>.json (derived data like events/drafts/risk is not seeded).
SEED_COLLECTIONS = [
    "clients",
    "trucks",
    "gps_pings",
    "shipments",
    "emails",
    "documents",
    "invoices",
    "payments",
    "incidents",
    "call_logs",
]

PAYLOAD_COLLECTION: dict[PayloadType, str] = {
    PayloadType.client: "clients",
    PayloadType.truck: "trucks",
    PayloadType.gps_ping: "gps_pings",
    PayloadType.shipment: "shipments",
    PayloadType.email: "emails",
    PayloadType.document: "documents",
    PayloadType.invoice: "invoices",
    PayloadType.payment: "payments",
    PayloadType.incident: "incidents",
    PayloadType.call_log: "call_logs",
}
