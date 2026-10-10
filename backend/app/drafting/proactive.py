"""Event -> draft glue: the proactive loop. Owner: C.
detect (B) -> profile (B) -> draft (C) -> queue -> human approves -> send (C).
"""

from app.drafting.service import generate_draft
from app.llm import LLMClient
from app.repository import Repository
from app.schemas import DomainEvent, DraftKind, DraftMessage, EventType, GenerateDraftRequest, Severity

EVENT_TO_DRAFT: dict[EventType, DraftKind] = {
    EventType.invoice_overdue: DraftKind.payment_reminder,
    EventType.shipment_delayed: DraftKind.delay_notice,
}
MIN_SEVERITY = {Severity.high, Severity.critical}  # medium events are listed but not auto-drafted


def draft_for_events(events: list[DomainEvent], repo: Repository, llm: LLMClient) -> list[DraftMessage]:
    drafts = []
    for ev in events:
        kind = EVENT_TO_DRAFT.get(ev.type)
        if kind is None or ev.severity not in MIN_SEVERITY or ev.draft_ids or not ev.client_id:
            continue
        draft = generate_draft(
            GenerateDraftRequest(
                kind=kind,
                client_id=ev.client_id,
                shipment_id=ev.shipment_id,
                invoice_id=ev.invoice_id,
                event_id=ev.id,
            ),
            repo,
            llm,
        )
        repo.events.upsert(ev.model_copy(update={"draft_ids": [*ev.draft_ids, draft.id]}))
        drafts.append(draft)
    # TODO(owner C): de-duplicate per client (one reminder covering several overdue invoices)
    return drafts
