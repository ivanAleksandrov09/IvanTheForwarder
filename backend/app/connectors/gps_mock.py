"""MOCK GPS CONNECTOR - replays fresh GPS pings for in-transit shipments. Owner: A.

Simulates a Traccar-like data source with positions updated every few minutes.
"""

from datetime import datetime

from app.connectors.base import BaseConnector
from app.repository import SeedStore
from app.schemas import ConnectorEnvelope, GpsPing, SourceType


class MockGpsConnector(BaseConnector):
    name = "gps.mock"
    source = SourceType.gps
    mode = "mock"
    description = "Replays fresh GPS positions for trucks in data/seed/gps_pings.json."

    def __init__(self, seed: SeedStore):
        super().__init__()
        self.seed = seed
        self._pings = None

    def fetch(self, since: datetime | None = None) -> list[ConnectorEnvelope]:
        # Load and parse GPS pings from seed data (cached on first load)
        if self._pings is None:
            raw_data = self.seed.load("gps_pings")
            self._pings = [GpsPing.model_validate(p) for p in raw_data]

        pings = self._pings
        if since is not None:
            pings = [p for p in pings if p.recorded_at > since]
        return [self.wrap(p, external_id=p.id) for p in pings]
