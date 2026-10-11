from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from app.core import clock
from app.core.config import Settings
from app.llm import LLMClient
from app.loads.search import LoadOffer, read_offers
from app.repository import Repository
from app.schemas import CallExtraction, CallExtractionContent, CallRecording


def _safe_filename(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(filename).name)
    return cleaned or f"recording_{uuid.uuid4().hex}.mp3"


_whisper_models: dict = {}


def transcribe(path: Path, settings: Settings, language: str | None = None) -> tuple[str, str]:
    if settings.whisper_model not in _whisper_models:
        import whisper  # heavy import (torch); only loaded when a recording is uploaded

        _whisper_models[settings.whisper_model] = whisper.load_model(settings.whisper_model)
    result = _whisper_models[settings.whisper_model].transcribe(str(path), language=language)
    return result["text"].strip(), f"whisper-{settings.whisper_model}"


def extract_call(call: CallRecording, repo: Repository, llm: LLMClient) -> CallExtraction:
    prompt = (
        "Extract logistics facts from this phone-call transcript. Use null for unknown values; never guess. "
        "Return dates as YYYY-MM-DD, weight in kg, price in whole EUR, and include short exact transcript quotes "
        "in evidence keyed by field. Identify missing fields needed to create a load. "
        f"TRANSCRIPT:\n{call.transcript}"
    )
    content, meta = llm.complete_json(
        task="call.extract",
        prompt=prompt,
        schema=CallExtractionContent,
        mock_context={"transcript": call.transcript},
    )
    return repo.call_extractions.upsert(
        CallExtraction(
            call_id=call.id,
            extracted_at=clock.now(),
            transcript=call.transcript or "",
            model=meta.model,
            **content.model_dump(),
        )
    )


def confirm_extraction(extraction: CallExtraction, repo: Repository, settings: Settings) -> CallExtraction:
    if extraction.status != "pending_review":
        raise ValueError(f"call extraction is already {extraction.status}")
    required = {
        "origin": extraction.origin,
        "destination": extraction.destination,
        "pickup_date": extraction.pickup_date,
        "cargo": extraction.cargo,
    }
    missing = [name for name, value in required.items() if value in (None, "")]
    if missing:
        raise ValueError(f"cannot confirm extraction; missing: {', '.join(missing)}")
    source_url = f"call://{extraction.call_id}"
    offers = read_offers()
    offer = LoadOffer(
        id=f"ld_call_{uuid.uuid4().hex[:12]}",
        origin=extraction.origin,
        destination=extraction.destination,
        pickup_date=extraction.pickup_date,
        cargo=extraction.cargo,
        weight_kg=extraction.weight_kg,
        vehicle=extraction.vehicle,
        price_eur=extraction.price_eur,
        source="phone_call",
        source_url=source_url,
        verified=False,
    )
    path = settings.runtime_dir / "loads.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([item.model_dump(mode="json") for item in offers] + [offer.model_dump(mode="json")], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return repo.call_extractions.upsert(extraction.model_copy(update={"status": "confirmed", "load_id": offer.id}))
