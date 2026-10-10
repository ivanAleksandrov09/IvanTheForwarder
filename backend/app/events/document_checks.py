"""Checks run once on every newly extracted document. Owner: B/C."""

import logging

from app.connectors.linking import link_by_company
from app.core import clock
from app.core.ids import stable_id
from app.drafting.document_context import due_date
from app.drafting.service import generate_draft
from app.llm import LLMClient
from app.repository import Repository
from app.schemas import (
    Document,
    DocumentType,
    DomainEvent,
    DraftKind,
    DraftStatus,
    EntityType,
    EventType,
    EvidenceRef,
    GenerateDraftRequest,
    InvoiceStatus,
    Severity,
)

log = logging.getLogger("forwarder.document_checks")
DUE_SOON_DAYS = 7
DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y")
NOT_YET_DUE = "This invoice is NOT overdue yet: write a friendly reminder that it falls due on the date given. Do not say it is overdue."


def _invoice_for(doc: Document, repo: Repository):
    number = doc.extracted_fields.get("invoice_number")
    return next(iter(repo.invoices.list(where=lambda i: i.number == number)), None) if number else None


def link_document(doc: Document, repo: Repository) -> Document:
    """Fill in a missing client link from the invoice record, else from the company name on the file. Never overwrites a link."""
    if doc.client_id is not None:
        return doc
    inv = _invoice_for(doc, repo)
    fields = doc.extracted_fields
    client_id = inv.client_id if inv else link_by_company(fields.get("receiver") or fields.get("customer_name"), repo)
    if client_id is None:
        return doc
    return repo.documents.upsert(doc.model_copy(update={"client_id": client_id, **({"invoice_id": inv.id} if inv else {})}))


def recheck_documents(repo: Repository, llm: LLMClient) -> None:
    """Re-run linking and the due-date check on every stored invoice, e.g. after clients changed.
    Works from the facts already extracted: no file is sent to the AI again."""
    now = clock.now()
    for doc in repo.documents.list(doc_type=DocumentType.invoice):
        try:
            check_invoice_due_soon(link_document(doc, repo), repo, llm, now)
        except Exception as exc:  # one bad document must not stop the rest
            log.warning("recheck of %s failed: %s", doc.filename, type(exc).__name__)


def check_invoice_due_soon(doc: Document, repo: Repository, llm: LLMClient, now) -> DomainEvent | None:
    """Invoice file due within DUE_SOON_DAYS (or already overdue) -> event, plus a reminder draft when the invoice is one of ours."""
    if doc.doc_type != DocumentType.invoice:
        return None
    due = due_date(doc.extracted_fields)
    if due is None:
        return None
    days = (due - now.date()).days
    if days > DUE_SOON_DAYS:
        return None

    number = doc.extracted_fields.get("invoice_number")
    inv = _invoice_for(doc, repo)
    if inv is not None and inv.status not in (InvoiceStatus.issued, InvoiceStatus.partially_paid):
        return None  # already paid or cancelled
    if inv is not None and days < 0:
        return None  # a known overdue invoice is already handled by the overdue detector
    fields = doc.extracted_fields
    client_id = inv.client_id if inv else (doc.client_id or link_by_company(fields.get("receiver") or fields.get("customer_name"), repo))
    overdue = days < 0
    etype = EventType.invoice_overdue if overdue else EventType.invoice_due_soon
    other = EventType.invoice_due_soon if overdue else EventType.invoice_overdue
    repo.events.delete(stable_id("evt", other, doc.id))  # the same file moved from "due soon" to "overdue" (or back)
    event_id = stable_id("evt", etype, doc.id)
    previous = repo.events.get(event_id)  # keep what the operator/drafting already did with it

    event = repo.events.upsert(
        DomainEvent(
            id=event_id,
            type=etype,
            severity=Severity.high if days <= -30 else Severity.medium,
            occurred_at=doc.received_at,
            detected_at=now,
            client_id=client_id,
            invoice_id=inv.id if inv else None,
            title=f"Invoice {number or doc.filename} is {-days} days overdue" if overdue else f"Invoice {number or doc.filename} is due in {days} days",
            description=f"{doc.filename}: due {due}, amount {doc.extracted_fields.get('total_amount', '?')} {doc.extracted_fields.get('currency', '')}.".strip(),
            data={"days_overdue": -days, "document": doc.filename} if overdue else {"days_until_due": days, "document": doc.filename},
            evidence=[EvidenceRef(entity_type=EntityType.document, entity_id=doc.id)],
            handled=previous.handled if previous else False,
            draft_ids=previous.draft_ids if previous else [],
        )
    )
    if client_id is None or event.draft_ids:
        return event  # nobody to address it to, or already drafted (even if the operator rejected it)
    pending = repo.drafts.list(
        where=lambda d: d.status in (DraftStatus.pending_review, DraftStatus.approved)
        and (d.event_id == event.id or (inv is not None and d.invoice_id == inv.id))
    )
    if pending:
        return event
    try:
        draft = generate_draft(
            GenerateDraftRequest(
                kind=DraftKind.payment_reminder,
                client_id=client_id,
                invoice_id=inv.id if inv else None,
                event_id=event.id,
                instructions=None if overdue else NOT_YET_DUE,
            ),
            repo,
            llm,
            document=None if inv else doc,
        )
        event = repo.events.upsert(event.model_copy(update={"draft_ids": [draft.id]}))
    except Exception as exc:  # the event stays; the operator can still draft by hand
        log.warning("reminder draft for %s failed: %s", doc.filename, type(exc).__name__)
    return event
