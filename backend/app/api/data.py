"""Read access to gathered data + connector control. Owner: A."""

from fastapi import APIRouter, Depends, HTTPException

from app.connectors.ingest import sync
from app.deps import get_connectors, get_repo
from app.repository import Repository
from app.schemas import (
    Client,
    ConnectorInfo,
    Document,
    Email,
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


@router.get("/connectors")
def list_connectors(connectors=Depends(get_connectors)) -> list[ConnectorInfo]:
    return [c.info() for c in connectors.values()]


@router.post("/connectors/{source}/sync")
def sync_connector(source: SourceType, repo: Repository = Depends(get_repo), connectors=Depends(get_connectors)) -> SyncResult:
    connector = connectors.get(source)
    if connector is None:
        raise HTTPException(404, f"no connector configured for {source}")
    return sync(connector, repo)
