"""Read access to gathered data + connector control. Owner: A."""

import imaplib
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.connectors import mailbox_store
from app.connectors.email_imap import ImapEmailConnector
from app.connectors.ingest import sync
from app.connectors.registry import use_imap, use_mock_email
from app.core.config import get_settings
from app.connectors.insights import analyze_email, process_new_emails
from app.deps import get_connectors, get_llm, get_repo, get_seed
from app.llm import LLMClient
from app.repository import Repository
from app.schemas import (
    Client,
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
