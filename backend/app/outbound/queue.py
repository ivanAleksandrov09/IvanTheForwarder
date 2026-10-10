"""Draft state machine: pending_review -> approved -> sent|failed ; pending_review -> rejected. Owner: C."""

from app.core import clock
from app.core.config import get_settings
from app.core.errors import ConflictError
from app.core.ids import new_id
from app.outbound.senders import build_sender
from app.repository import Repository
from app.schemas import Direction, DraftChannel, DraftMessage, DraftStatus, Email, UpdateDraftRequest

EDITABLE = {DraftStatus.pending_review}


def update_draft(draft_id: str, patch: UpdateDraftRequest, repo: Repository) -> DraftMessage:
    d = repo.drafts.require(draft_id)
    if d.status not in EDITABLE:
        raise ConflictError(f"draft is {d.status}, only pending_review drafts can be edited")
    changes = {k: v for k, v in patch.model_dump().items() if v is not None}
    return repo.drafts.upsert(d.model_copy(update=changes | {"updated_at": clock.now()}))


def approve_draft(draft_id: str, reviewed_by: str, repo: Repository) -> DraftMessage:
    d = repo.drafts.require(draft_id)
    if d.status != DraftStatus.pending_review:
        raise ConflictError(f"draft is {d.status}, cannot approve")
    if d.channel == DraftChannel.email and not d.to_addresses:
        raise ConflictError("draft has no recipient")
    now = clock.now()
    return repo.drafts.upsert(
        d.model_copy(update={"status": DraftStatus.approved, "reviewed_by": reviewed_by, "reviewed_at": now, "updated_at": now})
    )


def reject_draft(draft_id: str, reviewed_by: str, reason: str | None, repo: Repository) -> DraftMessage:
    d = repo.drafts.require(draft_id)
    if d.status != DraftStatus.pending_review:
        raise ConflictError(f"draft is {d.status}, cannot reject")
    now = clock.now()
    return repo.drafts.upsert(
        d.model_copy(
            update={
                "status": DraftStatus.rejected,
                "reviewed_by": reviewed_by,
                "reviewed_at": now,
                "rejection_reason": reason,
                "updated_at": now,
            }
        )
    )


def send_draft(draft_id: str, repo: Repository) -> DraftMessage:
    d = repo.drafts.require(draft_id)
    if d.status not in (DraftStatus.approved, DraftStatus.failed) or d.reviewed_at is None:
        raise ConflictError(f"draft is {d.status}: only human-approved drafts can be sent")
    s = get_settings()
    result = build_sender(s).send(d)
    now = clock.now()
    d = repo.drafts.upsert(
        d.model_copy(
            update={
                "status": DraftStatus.sent if result.ok else DraftStatus.failed,
                "send_result": result,
                "sent_at": result.sent_at,
                "updated_at": now,
            }
        )
    )
    if result.ok and d.channel == DraftChannel.email:  # keep the conversation history complete
        repo.emails.upsert(
            Email(
                id=new_id("eml"),
                mailbox=s.smtp_from or "office@vitosha-spedition.bg",
                direction=Direction.outbound,
                from_address=s.smtp_from or "office@vitosha-spedition.bg",
                from_name=s.operator_name,
                to_addresses=d.to_addresses,
                cc_addresses=d.cc_addresses,
                subject=d.subject or "",
                body_text=d.body,
                language=d.language,
                sent_at=now,
                client_id=d.client_id,
                shipment_id=d.shipment_id,
                labels=["sent_by_assistant", d.kind.value],
            )
        )
    if result.ok and d.event_id:
        event = repo.events.get(d.event_id)
        if event:
            repo.events.upsert(event.model_copy(update={"handled": True}))
    return d
