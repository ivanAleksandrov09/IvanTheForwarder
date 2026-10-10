"""Live GPS (Traccar) -> repo, and periodic status-update drafts."""

from datetime import timedelta

import httpx
import pytest

from app.connectors.gps_traccar import TraccarGpsConnector
from app.connectors.ingest import sync
from app.core import clock
from app.core.config import Settings
from app.deps import get_repo
from app.drafting.status_updates import draft_status_updates
from app.drafting.tracking import latest_ping
from app.schemas import DraftKind, GpsPing, ShipmentStatus


def _live_shipment(repo):
    return next(s for s in repo.shipments.list(status=ShipmentStatus.in_transit) if s.truck_id)


def _fresh_ping(repo, shipment, minutes_ago=5, speed=72.0):
    return repo.gps_pings.upsert(
        GpsPing(id=f"gps_t{minutes_ago:04d}", truck_id=shipment.truck_id, recorded_at=clock.now() - timedelta(minutes=minutes_ago),
                lat=shipment.destination.lat or 42.7, lon=shipment.destination.lon or 23.3, speed_kmh=speed)
    )


def test_status_update_drafted_once_per_interval(client):
    repo = get_repo()
    shp = _live_shipment(repo)
    _fresh_ping(repo, shp)
    first = client.post("/api/drafts/status-updates/run").json()
    mine = [d for d in first if d["shipment_id"] == shp.id]
    assert len(mine) == 1 and mine[0]["kind"] == "status_update" and mine[0]["status"] == "pending_review"
    assert mine[0]["to_addresses"], "drafted to the client's contact"
    again = client.post("/api/drafts/status-updates/run").json()
    assert not [d for d in again if d["shipment_id"] == shp.id]  # one pending draft per shipment, no stacking


def test_stale_gps_makes_no_draft(client):
    repo = get_repo()
    shp = _live_shipment(repo)
    for p in repo.gps_pings.list(truck_id=shp.truck_id):
        repo.gps_pings.delete(p.id)
    _fresh_ping(repo, shp, minutes_ago=300)  # 5h old
    assert not [d for d in draft_status_updates(repo, _llm()) if d.shipment_id == shp.id]


def test_disabled_with_zero_hours(client, monkeypatch):
    repo = get_repo()
    _fresh_ping(repo, _live_shipment(repo))
    monkeypatch.setenv("STATUS_UPDATE_HOURS", "0")
    from app.core import config
    config.get_settings.cache_clear()
    try:
        assert draft_status_updates(repo, _llm()) == []
    finally:
        config.get_settings.cache_clear()


def _llm():
    from app.deps import get_llm
    return get_llm()
