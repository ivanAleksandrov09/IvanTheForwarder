"""Periodic status updates: latest GPS position per truck -> one pending draft per in-transit shipment. Owner: A/C."""

from datetime import datetime, timedelta

from app.core import clock
from app.core.config import get_settings
from app.drafting.service import generate_draft
from app.drafting.tracking import STALE_PING, latest_ping
from app.llm import LLMClient
from app.repository import Repository
from app.schemas import DraftKind, DraftMessage, DraftStatus, GenerateDraftRequest, ShipmentStatus


def _recently_drafted(repo: Repository, shipment_id: str, now: datetime, interval: timedelta) -> bool:
    drafts = repo.drafts.list(where=lambda d: d.kind == DraftKind.status_update and d.shipment_id == shipment_id)
    return any(d.status == DraftStatus.pending_review or now - d.created_at < interval for d in drafts)


def draft_status_updates(repo: Repository, llm: LLMClient, now: datetime | None = None) -> list[DraftMessage]:
    """One pending draft per in-transit shipment with a fresh GPS position, at most every STATUS_UPDATE_HOURS. A human still approves."""
    hours = get_settings().status_update_hours
    if hours <= 0:
        return []
    now = now or clock.now()
    drafts = []
    for shipment in repo.shipments.list(status=ShipmentStatus.in_transit):
        ping = latest_ping(repo, shipment.truck_id) if shipment.truck_id else None
        if ping is None or now - ping.recorded_at > STALE_PING:
            continue
        if _recently_drafted(repo, shipment.id, now, timedelta(hours=hours)):
            continue
        client = repo.clients.get(shipment.client_id)
        if client is None or not any(c.email for c in client.contacts):
            continue  # nobody to send it to
        drafts.append(
            generate_draft(GenerateDraftRequest(kind=DraftKind.status_update, client_id=client.id, shipment_id=shipment.id), repo, llm)
        )
    return drafts
