"""Facts already extracted from a client's documents, as LLM context for drafting. Never re-reads the files."""

from app.repository import Repository

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
