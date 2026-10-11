from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.calls.service import _safe_filename, confirm_extraction, extract_call, transcribe
from app.core import clock
from app.core.config import get_settings
from app.core.ids import new_id
from app.deps import get_llm, get_repo
from app.llm import LLMClient
from app.repository import Repository
from app.schemas import CallExtraction, CallRecording, ConfirmCallRequest

router = APIRouter(prefix="/api/calls", tags=["calls"])


@router.post("/upload")
def upload_call(
    audio: UploadFile = File(...),
    language: str | None = Form(None),
    repo: Repository = Depends(get_repo),
    llm: LLMClient = Depends(get_llm),
) -> CallExtraction:
    if not audio.filename or not audio.filename.lower().endswith((".mp3", ".wav", ".m4a", ".ogg")):
        raise HTTPException(400, "upload an MP3, WAV, M4A, or OGG recording")
    settings = get_settings()
    call_id = new_id("cal")
    filename = f"{call_id}_{_safe_filename(audio.filename)}"
    path = settings.runtime_dir / "calls" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(audio.file.read())
    try:
        transcript, model = transcribe(path, settings, language)
        call = repo.call_recordings.upsert(
            CallRecording(
                id=call_id,
                filename=audio.filename,
                audio_path=str(path.relative_to(settings.runtime_dir)),
                content_type=audio.content_type or "audio/mpeg",
                uploaded_at=clock.now(),
                language=language,
                transcript=transcript,
                transcription_status="completed",
            )
        )
        return extract_call(call, repo, llm)
    except (RuntimeError, ValueError, OSError) as exc:
        raise HTTPException(502, str(exc)) from exc


@router.get("")
def list_calls(repo: Repository = Depends(get_repo)) -> list[CallRecording]:
    return repo.call_recordings.list()


@router.get("/{call_id}")
def get_call(call_id: str, repo: Repository = Depends(get_repo)) -> CallRecording:
    return repo.call_recordings.require(call_id)


@router.get("/{call_id}/extraction")
def get_extraction(call_id: str, repo: Repository = Depends(get_repo)) -> CallExtraction:
    return repo.call_extractions.require(call_id)


@router.post("/{call_id}/confirm")
def confirm_call(
    call_id: str,
    changes: ConfirmCallRequest | None = None,
    repo: Repository = Depends(get_repo),
) -> CallExtraction:
    extraction = repo.call_extractions.require(call_id)
    try:
        if changes:
            extraction = extraction.model_copy(update=changes.model_dump(exclude_unset=True))
        return confirm_extraction(extraction, repo, get_settings())
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
