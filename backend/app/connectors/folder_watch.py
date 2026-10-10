"""Watches a folder for new PDF/image files and stores what Claude extracts from them. Owner: A."""

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.core import clock
from app.core.config import Settings, get_settings
from app.core.ids import stable_id
from app.deps import get_llm, get_repo
from app.llm import LLMClient
from app.repository import Repository
from app.schemas import Document, DocumentType, SourceType

log = logging.getLogger("forwarder.folder_watch")

MIME_BY_SUFFIX = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
SETTLE_SECONDS = 5  # skip files modified this recently: they may still be being copied in

PROMPT = (
    "You read one document from a freight forwarder (CMR, invoice, rate sheet, transport order, "
    "proof of delivery, customs). Set doc_type to one of: cmr, invoice, rate_sheet, transport_order, pod, customs, other. "
    "Put every business fact you find into fields as snake_case keys with string values, for example invoice_number, "
    "total_amount, currency, issue_date, due_date, sender, receiver, route_origin, route_destination, gross_weight_kg, "
    "payment_terms_days, cmr_number, shipment_reference. Use ISO dates (YYYY-MM-DD) and plain numbers without units. "
    "Omit anything that is not in the document. Never guess. confidence is 0..1 for how sure you are overall."
)


class ExtractedDocument(BaseModel):
    doc_type: DocumentType
    confidence: float = Field(ge=0.0, le=1.0)
    fields: dict[str, Any] = {}


def scan_once(folder: Path, repo: Repository, llm: LLMClient) -> int:
    """Extracts every new or changed file in `folder`. Returns how many documents were stored."""
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
            extracted, _ = llm.extract_document(
                task="document.extract", data=path.read_bytes(), mime_type=mime, prompt=PROMPT, schema=ExtractedDocument
            )
        except Exception as exc:  # retried on the next scan: nothing is stored for this file
            log.warning("extraction failed for %s: %s", path.name, exc)
            continue
        repo.documents.upsert(
            Document(
                id=doc_id,
                doc_type=extracted.doc_type,
                filename=path.name,
                mime_type=mime,
                source=SourceType.documents,
                received_at=clock.now(),
                extracted_fields={k: str(v) for k, v in extracted.fields.items()},
                extraction_confidence=extracted.confidence,
            )
        )
        log.warning("extracted %s as %s", path.name, extracted.doc_type)
        stored += 1
    return stored


def tick(settings: Settings | None = None) -> None:
    s = settings or get_settings()
    scan_once(s.watch_folder, get_repo(), get_llm())


async def watch_loop(first_delay: float = 5) -> None:
    s = get_settings()
    if s.llm_mode != "live" or s.llm_provider != "anthropic":
        log.warning("folder watch off: needs LLM_MODE=live and LLM_PROVIDER=anthropic")
        return
    await asyncio.sleep(first_delay)
    while True:
        try:
            await asyncio.to_thread(tick, s)
        except Exception as exc:  # never let the loop die
            log.warning("folder watch failed: %s", type(exc).__name__)
        await asyncio.sleep(s.watch_interval_seconds)
