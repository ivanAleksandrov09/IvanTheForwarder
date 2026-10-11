"""Opt-in sharing of the company's capacity profile with the central network. Owner: lead."""

from fastapi import APIRouter, Depends, HTTPException

from app.company import effective
from app.core import clock
from app.core.config import get_settings
from app.core.errors import ConflictError
from app.deps import get_repo
from app.network import build_profile, settings_record
from app.publish import publish, withdraw
from app.repository import Repository
from app.schemas import ProfileSettings, ProfileSettingsInput, PublicProfileState

router = APIRouter(prefix="/api/network", tags=["network"])


def _state(repo: Repository) -> PublicProfileState:
    s = settings_record(repo)
    return PublicProfileState(settings=s, preview=build_profile(repo, effective(repo, get_settings()), s, clock.now()))


def _record(repo: Repository, s: ProfileSettings, status: str, **extra) -> None:
    repo.network_profile.upsert(s.model_copy(update={"last_publish_status": status, **extra}))


@router.get("/profile")
def get_profile(repo: Repository = Depends(get_repo)) -> PublicProfileState:
    """The saved choices plus a preview of exactly what would be sent."""
    return _state(repo)


@router.put("/profile")
def save_profile(body: ProfileSettingsInput, repo: Repository = Depends(get_repo)) -> PublicProfileState:
    current = settings_record(repo)
    repo.network_profile.upsert(
        ProfileSettings(**body.model_dump(), company_uid=current.company_uid, last_published_at=current.last_published_at,
                        last_publish_status=current.last_publish_status)
    )
    return _state(repo)


@router.post("/publish")
def publish_profile(repo: Repository = Depends(get_repo)) -> PublicProfileState:
    state = _state(repo)
    if not state.settings.consent:
        raise ConflictError("consent is required before anything is published")
    try:
        status = publish(state.preview, get_settings())
    except RuntimeError as exc:
        _record(repo, state.settings, f"failed: {exc}")
        raise HTTPException(502, str(exc)) from None
    _record(repo, state.settings, status, last_published_at=clock.now())
    return _state(repo)


@router.post("/withdraw")
def withdraw_profile(repo: Repository = Depends(get_repo)) -> PublicProfileState:
    """Stops all future sharing first, then asks the central index to delete what it holds."""
    s = settings_record(repo)
    s = repo.network_profile.upsert(s.model_copy(update={"consent": False}))
    try:
        status = withdraw(s.company_uid, get_settings())
    except RuntimeError as exc:
        _record(repo, s, f"withdraw failed, try again: {exc}")
        raise HTTPException(502, str(exc)) from None
    _record(repo, s, status, last_published_at=None)
    return _state(repo)
