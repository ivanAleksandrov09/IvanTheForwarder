"""Facts already extracted from a client's documents, as LLM context for drafting. Never re-reads the files."""

from datetime import UTC, date, datetime, time

from app.core.formatting import format_date
from app.repository import Repository
from app.schemas import Document, Language

DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y")

MAX_FIELDS = 12
FIELD_CHARS = 80


def _belongs(doc, client_id: str, invoice_numbers: set[str], references: set[str]) -> bool:
    if doc.client_id is not None:
        return doc.client_id == client_id
    f = doc.extracted_fields  # folder-extracted files have no client yet: match them by the numbers they mention
    return f.get("invoice_number") in invoice_numbers or bool({f.get("shipment_reference"), f.get("cmr_number")} & references)


def recent_documents(repo: Repository, client_id: str | None, shipment_id: str | None = None, limit: int = 5) -> list[dict]:
    """Most relevant documents of the client (documents of `shipment_id` first, then newest), oldest first."""
    if client_id is None:
        return []
    invoice_numbers = {i.number for i in repo.invoices.list(client_id=client_id)}
    shipments = repo.shipments.list(client_id=client_id)
    references = {s.reference for s in shipments} | {s.cmr_number for s in shipments if s.cmr_number}
    docs = [d for d in repo.documents.list() if d.extracted_fields and _belongs(d, client_id, invoice_numbers, references)]
    docs.sort(key=lambda d: (shipment_id is not None and d.shipment_id == shipment_id, d.received_at))
    return [
        {
            "type": d.doc_type.value,
            "received": d.received_at.strftime("%Y-%m-%d"),
            "file": d.filename,
            "confidence": d.extraction_confidence,
            "facts": {k: v[:FIELD_CHARS] for k, v in list(d.extracted_fields.items())[:MAX_FIELDS]},
        }
        for d in sorted(docs[-limit:], key=lambda d: d.received_at)
    ]


def due_date(fields: dict[str, str]) -> date | None:
    raw = (fields.get("due_date") or fields.get("maturity_date") or "").strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def document_invoice_context(doc: Document, language: Language, now: datetime) -> dict:
    """Invoice fields for a payment reminder built from a file: only facts the file states."""
    f = doc.extracted_fields
    due = due_date(f)
    ctx = {
        "invoice_number": f.get("invoice_number"),
        "invoice_total": " ".join(x for x in (f.get("total_amount"), f.get("currency")) if x) or None,
        "invoice_due": format_date(datetime.combine(due, time(12), tzinfo=UTC), language) if due else None,
    }
    if due is not None:
        days = (due - now.date()).days
        if days >= 0:
            ctx["days_until_due"] = days
        else:
            ctx["days_overdue"] = -days
    return ctx
