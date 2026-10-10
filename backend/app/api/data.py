"""Read access to gathered data + connector control. Owner: A."""

import imaplib
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.connectors import mailbox_store
from app.connectors.email_imap import ImapEmailConnector
from app.connectors.ingest import sync
from app.connectors.registry import use_imap, use_mock_email
from app.core import clock
from app.core.config import get_settings
from app.core.errors import ConflictError
from app.core.ids import new_id
from app.connectors.insights import analyze_email, process_new_emails
from app.company import effective, save as save_company
from app.events.document_checks import recheck_documents
from app.onboarding import build_emails
from app.schemas import CompanyInput, OnboardingEmail
from app.deps import get_connectors, get_llm, get_repo, get_seed
from app.llm import LLMClient
from app.repository import Repository
from app.schemas import (
    Client,
    DraftStatus,
    ClientInput,
    ConnectorInfo,
    Document,
    Email,
    EmailInsight,
    LinkEmailRequest,
    MailboxLoginRequest,
    MailboxProvider,
    MailboxStatus,
    GpsPing,
    Incident,
    Invoice,
    Payment,
    Shipment,
    ShipmentStatus,
    SourceType,
    SyncResult,
    Truck,
)

router = APIRouter(prefix="/api", tags=["data"])


@router.get("/clients")
def list_clients(repo: Repository = Depends(get_repo)) -> list[Client]:
    return repo.clients.list()


@router.get("/clients/{client_id}")
def get_client(client_id: str, repo: Repository = Depends(get_repo)) -> Client:
    return repo.clients.require(client_id)


@router.post("/clients")
def create_client(
    body: ClientInput, background: BackgroundTasks, repo: Repository = Depends(get_repo), llm: LLMClient = Depends(get_llm)
) -> Client:
    background.add_task(recheck_documents, repo, llm)  # a new client may match files already read
    return repo.clients.upsert(Client(id=new_id("cli"), created_at=clock.now(), **dict(body)))


@router.put("/clients/{client_id}")
def update_client(
    client_id: str, body: ClientInput, background: BackgroundTasks, repo: Repository = Depends(get_repo), llm: LLMClient = Depends(get_llm)
) -> Client:
    """Replace the editable fields; id and created_at are kept."""
    existing = repo.clients.require(client_id)
    background.add_task(recheck_documents, repo, llm)
    return repo.clients.upsert(Client(id=existing.id, created_at=existing.created_at, **dict(body)))


@router.delete("/clients/{client_id}", status_code=204)
def delete_client(client_id: str, background: BackgroundTasks, repo: Repository = Depends(get_repo), llm: LLMClient = Depends(get_llm)) -> None:
    """Refused while shipments, invoices, payments, incidents or sent/approved drafts belong to the client.
    Unsent drafts are removed with it; emails, documents and events are unlinked."""
    repo.clients.require(client_id)
    for name in ("shipments", "invoices", "payments", "incidents"):
        if repo.collection(name).list(client_id=client_id):
            raise ConflictError(f"client still has {name}: delete or reassign them first")
    drafts = repo.drafts.list(client_id=client_id)
    if any(d.status in (DraftStatus.approved, DraftStatus.sent) for d in drafts):
        raise ConflictError("client has approved or sent drafts: they must stay on record")
    unsent = {d.id for d in drafts}
    for draft in drafts:
        repo.drafts.delete(draft.id)
    for collection in (repo.emails, repo.documents, repo.call_logs, repo.events):
        for item in collection.list(client_id=client_id):
            update = {"client_id": None}
            if collection is repo.events:
                update["draft_ids"] = [d for d in item.draft_ids if d not in unsent]
            collection.upsert(item.model_copy(update=update))
    repo.risk_profiles.delete(client_id)
    repo.clients.delete(client_id)
    background.add_task(recheck_documents, repo, llm)


@router.get("/company")
def get_company(repo: Repository = Depends(get_repo)) -> CompanyInput:
    return effective(repo, get_settings())


@router.put("/company")
def put_company(body: CompanyInput, repo: Repository = Depends(get_repo), llm: LLMClient = Depends(get_llm)) -> CompanyInput:
    saved = save_company(repo, body)
    llm.set_company(saved.name, saved.operator_name)
    return effective(repo, get_settings())


@router.post("/onboarding/emails")
def onboarding_emails(language: Literal["en", "bg"] = "en", repo: Repository = Depends(get_repo)) -> list[OnboardingEmail]:
    """Draft one integration-access email per system saved in the company profile (ERP, GPS, other)."""
    return build_emails(effective(repo, get_settings()), language)


@router.get("/trucks")
def list_trucks(repo: Repository = Depends(get_repo)) -> list[Truck]:
    return repo.trucks.list()


@router.get("/trucks/{truck_id}/positions")
def truck_positions(truck_id: str, limit: int = 200, repo: Repository = Depends(get_repo)) -> list[GpsPing]:
    pings = sorted(repo.gps_pings.list(truck_id=truck_id), key=lambda p: p.recorded_at)
    return pings[-limit:]


@router.get("/shipments")
def list_shipments(
    status: ShipmentStatus | None = None, client_id: str | None = None, repo: Repository = Depends(get_repo)
) -> list[Shipment]:
    filters = {k: v for k, v in {"status": status, "client_id": client_id}.items() if v is not None}
    return repo.shipments.list(**filters)


@router.get("/shipments/{shipment_id}")
def get_shipment(shipment_id: str, repo: Repository = Depends(get_repo)) -> Shipment:
    return repo.shipments.require(shipment_id)


@router.get("/emails")
def list_emails(client_id: str | None = None, repo: Repository = Depends(get_repo)) -> list[Email]:
    items = repo.emails.list(client_id=client_id) if client_id else repo.emails.list()
    return sorted(items, key=lambda e: e.sent_at, reverse=True)


@router.get("/documents")
def list_documents(client_id: str | None = None, repo: Repository = Depends(get_repo)) -> list[Document]:
    return repo.documents.list(client_id=client_id) if client_id else repo.documents.list()


@router.get("/invoices")
def list_invoices(client_id: str | None = None, repo: Repository = Depends(get_repo)) -> list[Invoice]:
    return repo.invoices.list(client_id=client_id) if client_id else repo.invoices.list()


@router.get("/payments")
def list_payments(client_id: str | None = None, repo: Repository = Depends(get_repo)) -> list[Payment]:
    return repo.payments.list(client_id=client_id) if client_id else repo.payments.list()


@router.get("/incidents")
def list_incidents(client_id: str | None = None, repo: Repository = Depends(get_repo)) -> list[Incident]:
    return repo.incidents.list(client_id=client_id) if client_id else repo.incidents.list()


def _mailbox_status(connectors) -> MailboxStatus:
    connector = connectors.get(SourceType.email)
    creds = mailbox_store.load(get_settings())
    live = isinstance(connector, ImapEmailConnector) and creds is not None
    return MailboxStatus(
        connected=live,
        email=creds.username if live else None,
        provider=creds.provider if live and creds.provider in MailboxProvider._value2member_map_ else None,
        last_sync_at=connector.last_sync_at if connector else None,
        last_error=connector.last_error if connector else None,
    )


@router.get("/connectors/email/mailbox")
def mailbox_status(connectors=Depends(get_connectors)) -> MailboxStatus:
    return _mailbox_status(connectors)


@router.post("/connectors/email/login")
def mailbox_login(body: MailboxLoginRequest, connectors=Depends(get_connectors)) -> MailboxStatus:
    """Test the credentials, save them, and switch the email connector from mock to IMAP."""
    settings = get_settings()
    try:
        creds = mailbox_store.MailboxCredentials.for_provider(
            body.email, body.password, body.provider.value if body.provider else None
        )
    except ValueError:
        raise HTTPException(400, "Unknown email provider: choose Gmail or Outlook")
    connector = use_imap(connectors, settings)
    try:
        connector.test_login(creds)
    except (imaplib.IMAP4.error, OSError) as exc:
        use_mock_email(connectors, get_seed())
        raise HTTPException(400, f"Login failed: {exc}") from None  # never echo the password
    mailbox_store.save(settings, creds)
    return _mailbox_status(connectors)


@router.post("/connectors/email/logout")
def mailbox_logout(connectors=Depends(get_connectors)) -> MailboxStatus:
    mailbox_store.clear(get_settings())
    use_mock_email(connectors, get_seed())
    return _mailbox_status(connectors)


@router.get("/email-insights")
def list_email_insights(repo: Repository = Depends(get_repo)) -> list[EmailInsight]:
    """Background analysis results (one per analyzed email)."""
    return repo.email_insights.list()


@router.post("/emails/{email_id}/extract")
def extract_email(email_id: str, repo: Repository = Depends(get_repo), llm: LLMClient = Depends(get_llm)) -> EmailInsight:
    """Re-run the analysis for one email now (normally this happens automatically in the background)."""
    insight = analyze_email(email_id, repo, llm)
    if insight is None:
        raise HTTPException(502, "LLM unavailable: analysis not stored")
    return insight


@router.post("/emails/{email_id}/link")
def link_email(email_id: str, body: LinkEmailRequest, repo: Repository = Depends(get_repo)) -> Email:
    """Manually (un)link an email to a client. Survives re-sync."""
    if body.client_id:
        repo.clients.require(body.client_id)
    email = repo.emails.require(email_id)
    return repo.emails.upsert(email.model_copy(update={"client_id": body.client_id}))


@router.get("/connectors")
def list_connectors(connectors=Depends(get_connectors)) -> list[ConnectorInfo]:
    return [c.info() for c in connectors.values()]


@router.post("/connectors/{source}/sync")
def sync_connector(
    source: SourceType,
    background: BackgroundTasks,
    repo: Repository = Depends(get_repo),
    connectors=Depends(get_connectors),
    llm: LLMClient = Depends(get_llm),
) -> SyncResult:
    connector = connectors.get(source)
    if connector is None:
        raise HTTPException(404, f"no connector configured for {source}")
    result = sync(connector, repo)
    creds = mailbox_store.load(get_settings())
    if isinstance(connector, ImapEmailConnector) and creds:
        background.add_task(process_new_emails, repo, llm, creds.username)  # analysis never blocks the response
    return result
