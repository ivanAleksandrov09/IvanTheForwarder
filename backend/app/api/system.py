"""Health, LLM status/ping, demo reset. Owner: lead."""

from fastapi import APIRouter, Depends, HTTPException

from app.core import clock
from app.core.config import get_settings
from app.deps import get_llm, get_repo, get_seed
from app.llm import LLMClient
from app.repository import Repository, SeedStore
from app.repository.repo import load_seed_into
from app.schemas import SCHEMA_VERSION, HealthResponse, Language, LlmPingRequest, LlmPingResponse, LlmStatus, ResetResponse

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/health")
def health(llm: LLMClient = Depends(get_llm)) -> HealthResponse:
    s = get_settings()
    return HealthResponse(status="ok", app_env=s.app_env, schema_version=SCHEMA_VERSION, now=clock.now(), llm=llm.status())


@router.get("/llm")
def llm_status(llm: LLMClient = Depends(get_llm)) -> LlmStatus:
    return llm.status()


@router.post("/llm/ping")
def llm_ping(body: LlmPingRequest, llm: LLMClient = Depends(get_llm)) -> LlmPingResponse:
    """Hello-world LLM call. Use it to verify a provider key: set LLM_MODE=live and call this."""
    lang = body.language or Language.bg
    reply, meta = llm.complete_text(
        task="system.ping", prompt=f"[language={lang.value}] {body.message}", mock_context={"language": lang.value}
    )
    return LlmPingResponse(reply=reply, llm=meta)


@router.post("/reset")
def reset_demo(repo: Repository = Depends(get_repo), seed: SeedStore = Depends(get_seed)) -> ResetResponse:
    """Wipe the DB. Reloads the mock data/seed only when AUTO_SEED is on (tests and demos)."""
    if get_settings().app_env not in ("dev", "demo", "test"):
        raise HTTPException(403, "reset disabled")
    repo.wipe()
    loaded = load_seed_into(repo, seed) if get_settings().auto_seed else {}
    return ResetResponse(collections=loaded)
