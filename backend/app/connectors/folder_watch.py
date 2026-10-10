"""Watches incoming files and stores the invoice facts they state. Searchable PDFs are read locally (Zeron-style
and simple labelled invoices); anything else goes to Claude when LLM_MODE=live. Owner: A."""

import asyncio
import logging
import re
import time
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pypdf import PdfReader

from app.core import clock
from app.core.config import Settings, get_settings
from app.core.ids import stable_id
from app.deps import get_llm, get_repo
from app.events.document_checks import check_invoice_due_soon
from app.llm import LLMClient
from app.repository import Repository
from app.schemas import Client, Document, DocumentType, Language, SourceType

log = logging.getLogger("forwarder.folder_watch")

MIME_BY_SUFFIX = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}
SETTLE_SECONDS = 5  # skip files modified this recently: they may still be being copied in
MAX_ATTEMPTS = 3  # a file that keeps failing is left alone until the backend restarts (no endless paid retries)
_failures: dict[str, int] = {}

_INVOICE_NUMBER = re.compile(
    r"\b(?:invoice|фактура)\s*(?:(?:no\.?|number|№)|#)?\s*[:#№]?\s*([0-9]{10})\b",
    re.IGNORECASE,
)
_NUMBER_AFTER_NO = re.compile(r"\bNo\.\s*([0-9]{10})\b")  # Zeron layout: "No.      0000013757"
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[./]\d{1,2}[./]\d{4}\b")
_ISSUE_DATE = re.compile(
    rf"(?<!maturity )(?<!до )(?<!due )\b(?:date|дата)\b\s*[:#]?\s*({_DATE.pattern})", re.IGNORECASE
)
_DUE_DATE = re.compile(
    rf"\b(?:due|падеж|maturity\s+date|срок\s+на\s+плащане\s+до\s+дата)\b\s*[:#]?\s*({_DATE.pattern})",
    re.IGNORECASE,
)
_TOTAL = re.compile(
    r"\b(?:total|общо|сума\s+за\s+плащане|amount\s+to\s+pay)\b\s*[:#]?\s*([0-9][0-9 ,.]*[0-9]|[0-9])",
    re.IGNORECASE,
)
_CURRENCY = re.compile(r"\b(EUR|BGN|USD|GBP)\b|(лв\.?|евро)", re.IGNORECASE)
_CUSTOMER_LABEL = re.compile(r"\b(?:client|customer|клиент)\s*:", re.IGNORECASE)
# The billed party is on the left of the Zeron layout, so its VAT number comes before the supplier's.
_CUSTOMER_VAT = re.compile(r"\b(?:ДДС\s*No\.?|VAT\s*No\.?)\s*:\s*([A-Z]{2}[0-9]{8,12})\b")

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


def _iso(value: str) -> str:
    parts = value.replace(".", "-").replace("/", "-").split("-")
    if len(parts[0]) == 4:
        return "-".join(parts)
    return f"{parts[2]}-{int(parts[1]):02d}-{int(parts[0]):02d}"


def _parse_iso(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _amount(raw: str) -> str:
    amount = raw.replace(" ", "")
    if "," in amount and "." in amount:
        decimal = "," if amount.rfind(",") > amount.rfind(".") else "."
        grouping = "." if decimal == "," else ","
        return amount.replace(grouping, "").replace(decimal, ".")
    return amount.replace(",", ".")


def _chunks(line: str) -> list[str]:
    """Columns of a layout line: pieces separated by two or more spaces."""
    return [chunk for chunk in re.split(r"\s{2,}", line.strip()) if chunk]


def _customer(lines: list[str]) -> tuple[str | None, str | None]:
    """Name and city of the billed party: the text after the label, else the line below it (Zeron layout)."""
    for i, line in enumerate(lines):
        match = _CUSTOMER_LABEL.search(line)
        if match is None:
            continue
        chunks = _chunks(line[match.end() :])
        if chunks and not chunks[0].endswith(":"):
            return chunks[0], None  # plain text: "Client: Name" on one line, no city given
        below = _chunks(lines[i + 1]) if i + 1 < len(lines) else []
        if not below:
            return None, None
        city_chunks = _chunks(lines[i + 2]) if i + 2 < len(lines) else []
        city = city_chunks[0] if city_chunks and re.fullmatch(r"[^\d:]+", city_chunks[0]) else None
        return below[0], city
    return None, None


def _local_invoice_fields(text: str) -> dict[str, str]:
    """Invoice facts from plain labelled text, or from Zeron invoices extracted in layout mode."""
    fields: dict[str, str] = {}
    if match := (_INVOICE_NUMBER.search(text) or _NUMBER_AFTER_NO.search(text)):
        fields["invoice_number"] = match.group(1)
    if match := _ISSUE_DATE.search(text):
        fields["issue_date"] = _iso(match.group(1))
    if match := _DUE_DATE.search(text):
        fields["due_date"] = _iso(match.group(1))
    if match := _TOTAL.search(text):
        fields["total_amount"] = _amount(match.group(1))
        if currency := _CURRENCY.search(text):
            if currency.group(1):
                fields["currency"] = currency.group(1).upper()
            else:
                fields["currency"] = "BGN" if currency.group(2).lower().startswith("лв") else "EUR"

    name, city = _customer(text.splitlines())
    if name:
        fields["client_name"] = name
    if city:
        fields["customer_city"] = city
    if match := _CUSTOMER_VAT.search(text):
        fields["customer_vat"] = match.group(1)
    return fields


def _link_document(document: Document, repo: Repository) -> Document:
    """Link only on unique exact invoice, shipment, VAT number, or client-name matches."""
    fields = document.extracted_fields
    client_ids: set[str] = set()
    invoice_matches = repo.invoices.list(number=fields["invoice_number"]) if fields.get("invoice_number") else []
    shipment_matches = (
        repo.shipments.list(reference=fields["shipment_reference"]) if fields.get("shipment_reference") else []
    )
    if len(invoice_matches) == 1:
        client_ids.add(invoice_matches[0].client_id)
    if len(shipment_matches) == 1:
        client_ids.add(shipment_matches[0].client_id)

    if vat := fields.get("customer_vat"):
        vat_matches = [client for client in repo.clients.list() if client.vat_number == vat]
        if len(vat_matches) == 1:
            client_ids.add(vat_matches[0].id)

    client_name = fields.get("client_name") or fields.get("customer_name") or fields.get("bill_to")
    if client_name:
        normalized = _normalise_name(client_name)
        name_matches = [
            client
            for client in repo.clients.list()
            if normalized in {_normalise_name(client.name), _normalise_name(client.name_latin or "")}
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


def _client_from_invoice(document: Document, repo: Repository) -> str | None:
    """A billed party named on an invoice becomes a client. Only facts the file states: VAT number, country (from
    the VAT prefix), city, and payment terms (due date minus issue date). Without all of them, nothing is created."""
    fields = document.extracted_fields
    vat, name = fields.get("customer_vat"), fields.get("client_name")
    issued, due = _parse_iso(fields.get("issue_date")), _parse_iso(fields.get("due_date"))
    if not (vat and name and issued and due) or due < issued:
        return None
    country = vat[:2]
    client = Client(
        id=stable_id("cli", vat),
        name=name,
        vat_number=vat,
        country=country,
        city=fields.get("customer_city", ""),
        preferred_language=Language.bg if country == "BG" else Language.en,
        payment_terms_days=(due - issued).days,
        created_at=clock.now(),
    )
    log.info("new client %s from invoice %s", client.name, document.filename)
    return repo.clients.upsert(client).id


def _pdf_text(path: Path) -> str:
    # layout mode keeps "label      value" on one line, which the invoice labels rely on
    return "\n".join(page.extract_text(extraction_mode="layout") or "" for page in PdfReader(path).pages)


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
        fields = _local_invoice_fields(_pdf_text(path))
        if fields.get("invoice_number"):
            confidence = 0.9 if {"invoice_number", "due_date"} <= fields.keys() else 0.65
            return ExtractedDocument(doc_type=DocumentType.invoice, confidence=confidence, fields=fields), "local-pdf"
    raise RuntimeError(
        "No searchable invoice data found; configure live Anthropic extraction for scanned or other documents"
    )


def scan_once(folder: Path, repo: Repository, llm: LLMClient) -> int:
    """Extracts new files, links them to clients (creating the client from an invoice when it is new) and runs the
    due-date check. Returns how many documents were stored."""
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
        if repo.documents.get(doc_id) is not None or _failures.get(doc_id, 0) >= MAX_ATTEMPTS:
            continue  # already analyzed (or given up): only new or changed files cost an API call
        try:
            extracted, method = _extract(path, mime, llm)
        except Exception as exc:  # nothing is stored; retried on later scans up to MAX_ATTEMPTS
            _failures[doc_id] = _failures.get(doc_id, 0) + 1
            log.warning("extraction failed for %s (attempt %d/%d): %s", path.name, _failures[doc_id], MAX_ATTEMPTS, exc)
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
        document = _link_document(document, repo)
        if document.client_id is None and document.doc_type == DocumentType.invoice:
            if client_id := _client_from_invoice(document, repo):
                document = document.model_copy(update={"client_id": client_id})
        document = repo.documents.upsert(document)
        log.info("extracted %s as %s via %s", path.name, extracted.doc_type, method)
        try:
            check_invoice_due_soon(document, repo, llm, clock.now())
        except Exception as exc:  # the document stays stored; only its event/draft is skipped
            log.warning("due-date check failed for %s: %s", path.name, type(exc).__name__)
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
