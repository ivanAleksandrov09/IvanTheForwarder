"""GPS helpers shared by drafting. Owner: A/C."""

import math
from datetime import timedelta

from app.repository import Repository
from app.schemas import GpsPing, Shipment

MOVING_KMH = 5.0
STALE_PING = timedelta(hours=2)  # an older position would make the update wrong, so no draft is made


def latest_ping(repo: Repository, truck_id: str) -> GpsPing | None:
    pings = repo.gps_pings.list(truck_id=truck_id)
    return max(pings, key=lambda p: p.recorded_at) if pings else None


def remaining_km(ping: GpsPing, shipment: Shipment) -> float | None:
    """Straight-line km to the destination (roads are longer, so the draft says 'approximately'); capped at the route length."""
    dest = shipment.destination
    if dest.lat is None or dest.lon is None:
        return None
    p1, p2 = math.radians(ping.lat), math.radians(dest.lat)
    dphi, dlam = p2 - p1, math.radians(dest.lon - ping.lon)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return min(6371 * 2 * math.asin(math.sqrt(a)), shipment.distance_km)
