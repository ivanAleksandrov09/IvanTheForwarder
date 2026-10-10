"""Watches incoming files, locally parses searchable invoices, and uses Claude for richer extraction. Owner: A."""

import asyncio
import logging
import re
import time
import unicodedata
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.core import clock
from app.core.config import Settings, get_settings
from app.core.ids import stable_id
from app.deps import get_llm, get_repo
from app.llm import LLMClient, LLMError
from app.repository import Repository
from app.schemas import Document, DocumentType, SourceType

log = logging.getLogger("forwarder.folder_watch")

MIME_BY_SUFFIX = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}
SETTLE_SECONDS = 5  # skip files modified this recently: they may still be being copied in
_INVOICE_NUMBER = re.compile(
    r"\b(?:invoice|фактура)\s*(?:(?:no\.?|number|№)|#)?\s*[:#№]?\s*([0-9]{10})\b",
    re.IGNORECASE,
)
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[./]\d{1,2}[./]\d{4}\b")

PROMPT = (
    "You read one document from a freight forwarder (CMR, invoice, rate sheet, transport order, "
    "proof of delivery, customs). Set doc_type to one of: cmr, invoice, rate_sheet, transport_order, pod, customs, other. "
    "Put every business fact you find into fields as snake_case keys with string values, for example invoice_number, "
    "total_amount, currency, issue_date, due_date, sender, receiver, route_origin, route_destination, gross_weight_kg, "
    "payment_terms_days, cmr_number, shipment_reference, client_name. For invoices, client_name is the billed "
    "customer, not the seller. Use ISO dates (YYYY-MM-DD) and plain numbers without units. "
    "Omit anything that is not in the document. Never guess. confidence is 0..1 for how sure you are overall."
)


class ExtractedDocument(BaseModel):
    doc_type: DocumentType
    confidence: float = Field(ge=0.0, le=1.0)
    fields: dict[str, Any] = {}


def _normalise_name(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _local_invoice_fields(text: str) -> dict[str, str]:
    """Extract common searchable invoice fields without an external model."""
    fields: dict[str, str] = {}
    if match := _INVOICE_NUMBER.search(text):
        fields["invoice_number"] = match.group(1)

    def date_after(label: str, field: str) -> None:
        match = re.search(rf"\b(?:{label})\b\s*[:#]?\s*({_DATE.pattern})", text, re.IGNORECASE)
        if match:
            value = match.group(1).replace(".", "-").replace("/", "-")
            parts = value.split("-")
            if len(parts[0]) != 4:
                value = f"{parts[2]}-{int(parts[1]):02d}-{int(parts[0]):02d}"
            fields[field] = value

    date_after("date|дата", "issue_date")
    date_after("due|падеж", "due_date")

    if match := re.search(
        r"\b(?:total|общо|сума(?:\s+за\s+плащане)?)\b\s*[:#]?\s*"
        r"([0-9][0-9 ,.]*[0-9]|[0-9])\s*(EUR|BGN|USD|GBP|лв\.?|евро)\b",
        text,
        re.IGNORECASE,
    ):
        amount = match.group(1).replace(" ", "")
        if "," in amount and "." in amount:
            decimal_separator = "," if amount.rfind(",") > amount.rfind(".") else "."
            grouping_separator = "." if decimal_separator == "," else ","
            amount = amount.replace(grouping_separator, "").replace(decimal_separator, ".")
        elif "," in amount:
            amount = amount.replace(",", ".")
        fields["total_amount"] = amount
        currency = match.group(2).upper()
        fields["currency"] = "BGN" if currency.startswith("ЛВ") else "EUR" if currency == "ЕВРО" else currency

    if match := re.search(
        r"\b(?:client|customer|bill\s+to|клиент|получател)\s*[:#]?\s*([^\r\n]+)",
        text,
        re.IGNORECASE,
    ):
        fields["client_name"] = match.group(1)
    return fields


def _link_document(document: Document, repo: Repository) -> Document:
    """Link only on unique exact invoice, shipment, or client-name matches."""
    fields = document.extracted_fields
    client_ids: set[str] = set()
    invoice_matches = (
        repo.invoices.list(number=fields["invoice_number"]) if fields.get("invoice_number") else []
    )
    shipment_matches = (
        repo.shipments.list(reference=fields["shipment_reference"])
        if fields.get("shipment_reference")
        else []
    )
    if len(invoice_matches) == 1:
        client_ids.add(invoice_matches[0].client_id)
    if len(shipment_matches) == 1:
        client_ids.add(shipment_matches[0].client_id)

    client_name = fields.get("client_name") or fields.get("customer_name") or fields.get("bill_to")
    if client_name:
        normalized = _normalise_name(client_name)
        name_matches = [
            client
            for client in repo.clients.list()
            if normalized
            in {
                _normalise_name(client.name),
                _normalise_name(client.name_latin or ""),
            }
        ]
        if len(name_matches) == 1:
            client_ids.add(name_matches[0].id)
        elif len(name_matches) > 1:
            log.warning("not linking %s: customer name is ambiguous", document.filename)

    if len(client_ids) != 1:
        if len(client_ids) > 1:
            log.warning("not linking %s: extracted references point to different clients", document.filename)
        return document

    client_id = next(iter(client_ids))
    invoice = next((item for item in invoice_matches if item.client_id == client_id), None)
    shipment = next((item for item in shipment_matches if item.client_id == client_id), None)
    return document.model_copy(
        update={
            "client_id": client_id,
            "invoice_id": invoice.id if invoice else document.invoice_id,
            "shipment_id": shipment.id if shipment else document.shipment_id,
        }
    )


def _extract(path: Path, mime: str, llm: LLMClient) -> tuple[ExtractedDocument, str]:
    settings = llm.s
    if settings.llm_mode == "live" and settings.llm_provider == "anthropic":
        extracted, _ = llm.extract_document(
            task="document.extract",
            data=path.read_bytes(),
            mime_type=mime,
            prompt=PROMPT,
            schema=ExtractedDocument,
        )
        return extracted, "anthropic"

    if mime == "application/pdf":
        text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
        fields = _local_invoice_fields(text)
        if fields:
            confidence = 0.9 if {"invoice_number", "due_date"} <= fields.keys() else 0.65
            return ExtractedDocument(
                doc_type=DocumentType.invoice, confidence=confidence, fields=fields
            ), "local-pdf"
    raise RuntimeError(
        "No searchable invoice data found; configure live Anthropic extraction for scanned or other documents"
    )


def scan_once(folder: Path, repo: Repository, llm: LLMClient) -> int:
    """Extracts new PDFs, links unambiguous clients and stores the resulting documents."""
    folder.mkdir(parents=True, exist_ok=True)
    stored = 0
    for path in sorted(folder.iterdir()):
        mime = MIME_BY_SUFFIX.get(path.suffix.lower())
        if mime is None or not path.is_file():
            continue
        st = path.stat()
        if time.time() - st.st_mtime < SETTLE_SECONDS:
            continue
        doc_id = stable_id("doc", path.name, str(st.st_size), str(st.st_mtime_ns))
        if repo.documents.get(doc_id) is not None:
            continue
        try:
            extracted, _method = _extract(path, mime, llm)
        except (LLMError, OSError, PdfReadError, RuntimeError, ValidationError) as exc:
            # Retried on the next scan; do not store a partial or invalid extraction.
            log.warning("extraction failed for %s: %s", path.name, exc)
            continue
        document = Document(
            id=doc_id,
            doc_type=extracted.doc_type,
            filename=path.name,
            mime_type=mime,
            source=SourceType.documents,
            received_at=clock.now(),
            extracted_fields={k: str(v) for k, v in extracted.fields.items()},
            extraction_confidence=extracted.confidence,
        )
        repo.documents.upsert(_link_document(document, repo))
        log.info("extracted %s as %s via %s", path.name, extracted.doc_type, _method)
        stored += 1
    return stored


def tick(settings: Settings | None = None) -> None:
    s = settings or get_settings()
    scan_once(s.watch_folder, get_repo(), get_llm())


async def watch_loop(first_delay: float = 5) -> None:
    s = get_settings()
    await asyncio.sleep(first_delay)
    while True:
        try:
            await asyncio.to_thread(tick, s)
        except Exception as exc:  # noqa: BLE001  # a background watch loop must survive individual scan failures
            log.warning("folder watch failed: %s", type(exc).__name__)
        await asyncio.sleep(s.watch_interval_seconds)
