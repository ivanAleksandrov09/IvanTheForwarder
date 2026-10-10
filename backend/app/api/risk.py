"""Risk profiles and events. Owner: B."""

from fastapi import APIRouter, Depends

from app.core import clock
from app.deps import get_llm, get_repo
from app.drafting.proactive import draft_for_events
from app.events.detectors import run_detectors
from app.llm import LLMClient
from app.repository import Repository
from app.risk.scoring import get_profile
from app.schemas import DomainEvent, RiskProfile

router = APIRouter(prefix="/api", tags=["risk"])


@router.get("/risk")
def list_risk_profiles(repo: Repository = Depends(get_repo)) -> list[RiskProfile]:
    now = clock.now()
    return [get_profile(c.id, repo, now) for c in repo.clients.list()]


@router.get("/clients/{client_id}/risk")
def client_risk(client_id: str, repo: Repository = Depends(get_repo)) -> RiskProfile:
    return get_profile(client_id, repo, clock.now())


@router.get("/events")
def list_events(repo: Repository = Depends(get_repo)) -> list[DomainEvent]:
    return sorted(repo.events.list(), key=lambda e: e.detected_at, reverse=True)


@router.post("/events/scan")
def scan(auto_draft: bool = True, repo: Repository = Depends(get_repo), llm: LLMClient = Depends(get_llm)) -> list[DomainEvent]:
    """Run all detectors; with auto_draft, new actionable events get a draft in the approval queue."""
    current, _new = run_detectors(repo, clock.now())
    if auto_draft:
        draft_for_events(current, repo, llm)
    return sorted(repo.events.list(), key=lambda e: e.detected_at, reverse=True)
