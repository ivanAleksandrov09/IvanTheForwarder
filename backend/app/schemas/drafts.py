"""Outgoing communication. Nothing leaves the system unless status == approved (enforced in outbound/)."""

from pydantic import Field

from app.schemas.common import (
    ClientId,
    ContractModel,
    DocumentId,
    DraftId,
    EmailAddress,
    EventId,
    InvoiceId,
    ShipmentId,
    UtcDatetime,
)
from app.schemas.enums import DraftChannel, DraftKind, DraftStatus, Language, LlmMode, Tone


class LlmMeta(ContractModel):
    mode: LlmMode
    model: str
    used_fallback: bool = False  # true = live call failed and the canned response was used
    log_id: str | None = None  # line in data/runtime/logs/llm.jsonl
    latency_ms: int | None = None


class SendResult(ContractModel):
    ok: bool
    provider: str  # "log" | "smtp" | ...
    sent_at: UtcDatetime | None = None
    provider_message_id: str | None = None
    error: str | None = None


class DraftMessage(ContractModel):
    """A.k.a. NotificationItem: one entry in the "ready to send" queue."""

    id: DraftId
    kind: DraftKind
    channel: DraftChannel
    status: DraftStatus
    language: Language
    tone: Tone
    client_id: ClientId | None = None
    shipment_id: ShipmentId | None = None
    invoice_id: InvoiceId | None = None
    event_id: EventId | None = None
    to_addresses: list[EmailAddress] = []
    cc_addresses: list[EmailAddress] = []
    subject: str | None = None  # null for sms/viber
    body: str
    attachment_document_ids: list[DocumentId] = []
    rationale: str  # why the assistant drafted this, shown to the human reviewer
    created_at: UtcDatetime
    updated_at: UtcDatetime
    reviewed_by: str | None = None
    reviewed_at: UtcDatetime | None = None
    rejection_reason: str | None = None
    sent_at: UtcDatetime | None = None
    send_result: SendResult | None = None
    llm: LlmMeta | None = None


class DraftContent(ContractModel):
    """The JSON the LLM must return when drafting. Validated by llm.complete_json()."""

    subject: str
    body: str
    language: Language
    tone: Tone
    rationale: str = Field(description="1-2 sentences for the human reviewer: why this message, why this tone")


# ---------- request bodies ----------
class GenerateDraftRequest(ContractModel):
    kind: DraftKind
    client_id: ClientId
    shipment_id: ShipmentId | None = None
    invoice_id: InvoiceId | None = None
    event_id: EventId | None = None
    language: Language | None = None  # default: client.preferred_language
    tone: Tone | None = None  # default: risk_profile.recommended_tone
    instructions: str | None = None  # free text from the operator, e.g. "mention the new rate"


class UpdateDraftRequest(ContractModel):
    """PATCH semantics: null/omitted = unchanged (the one place where null means 'not provided')."""

    subject: str | None = None
    body: str | None = None
    to_addresses: list[EmailAddress] | None = None
    cc_addresses: list[EmailAddress] | None = None


class ApproveDraftRequest(ContractModel):
    reviewed_by: str = "operator"


class RejectDraftRequest(ContractModel):
    reviewed_by: str = "operator"
    reason: str | None = None
