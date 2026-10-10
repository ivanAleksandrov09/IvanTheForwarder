"""The "ready to send" queue. Owner: C."""

from fastapi import APIRouter, Depends

from app.deps import get_llm, get_repo
from app.drafting.service import generate_draft
from app.llm import LLMClient
from app.outbound.queue import approve_draft, reject_draft, send_draft, update_draft
from app.repository import Repository
from app.schemas import (
    ApproveDraftRequest,
    DraftMessage,
    DraftStatus,
    GenerateDraftRequest,
    RejectDraftRequest,
    UpdateDraftRequest,
)

router = APIRouter(prefix="/api/drafts", tags=["drafts"])


@router.get("")
def list_drafts(status: DraftStatus | None = None, repo: Repository = Depends(get_repo)) -> list[DraftMessage]:
    items = repo.drafts.list(status=status) if status else repo.drafts.list()
    return sorted(items, key=lambda d: d.created_at, reverse=True)


@router.post("/generate")
def generate(req: GenerateDraftRequest, repo: Repository = Depends(get_repo), llm: LLMClient = Depends(get_llm)) -> DraftMessage:
    return generate_draft(req, repo, llm)


@router.get("/{draft_id}")
def get_draft(draft_id: str, repo: Repository = Depends(get_repo)) -> DraftMessage:
    return repo.drafts.require(draft_id)


@router.patch("/{draft_id}")
def edit_draft(draft_id: str, patch: UpdateDraftRequest, repo: Repository = Depends(get_repo)) -> DraftMessage:
    return update_draft(draft_id, patch, repo)


@router.post("/{draft_id}/approve")
def approve_and_send(draft_id: str, body: ApproveDraftRequest, repo: Repository = Depends(get_repo)) -> DraftMessage:
    """The human confirmation step. Approves, then sends immediately."""
    approve_draft(draft_id, body.reviewed_by, repo)
    return send_draft(draft_id, repo)


@router.post("/{draft_id}/reject")
def reject(draft_id: str, body: RejectDraftRequest, repo: Repository = Depends(get_repo)) -> DraftMessage:
    return reject_draft(draft_id, body.reviewed_by, body.reason, repo)


@router.post("/{draft_id}/send")
def retry_send(draft_id: str, repo: Repository = Depends(get_repo)) -> DraftMessage:
    """Retry a failed send. Refuses anything not already approved by a human."""
    return send_draft(draft_id, repo)
