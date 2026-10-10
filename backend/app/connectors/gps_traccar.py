"""Live GPS connector for a Traccar server."""

from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx

from app.connectors.base import BaseConnector
from app.core import clock
from app.core.config import Settings
from app.core.ids import stable_id
from app.schemas import ConnectorEnvelope, ConnectorHealth, GpsPing, SourceType


class TraccarGpsConnector(BaseConnector):
    name = "gps.traccar"
    source = SourceType.gps
    mode = "live"
    description = "Reads vehicle positions from a Traccar server."

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.device_map = self._parse_device_map(settings.traccar_device_map)

    @staticmethod
    def _parse_device_map(value: str) -> dict[int, str]:
        mapping: dict[int, str] = {}
        for item in filter(None, (part.strip() for part in value.split(","))):
            try:
                device_id, truck_id = item.split(":", 1)
                mapping[int(device_id.strip())] = truck_id.strip()
            except ValueError as exc:
                raise ValueError(f"invalid TRACCAR_DEVICE_MAP entry {item!r}; expected device_id:truck_id") from exc
        return mapping

    def health(self) -> ConnectorHealth:
        if not self.settings.traccar_url or not self.device_map:
            return ConnectorHealth.disabled
        return ConnectorHealth.ok

    def fetch(self, since: datetime | None = None) -> list[ConnectorEnvelope]:
        if not self.settings.traccar_url:
            raise ValueError("TRACCAR_URL is required when CONNECTOR_GPS=traccar")
        if not self.device_map:
            raise ValueError("TRACCAR_DEVICE_MAP is required when CONNECTOR_GPS=traccar")

        params: dict[str, str] = {"deviceId": ",".join(str(device_id) for device_id in self.device_map)}
        if since is not None:
            params["from"] = since.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        params["to"] = clock.now().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        headers = {"Accept": "application/json"}
        if self.settings.traccar_token:
            headers["Authorization"] = f"Bearer {self.settings.traccar_token}"
        auth = (self.settings.traccar_user, self.settings.traccar_password) if self.settings.traccar_user else None
        url = self.settings.traccar_url.rstrip("/") + "/api/positions?" + urlencode(params)

        try:
            response = httpx.get(url, headers=headers, auth=auth, timeout=15.0)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Traccar request failed: {exc}") from exc

        try:
            positions = response.json()
        except ValueError as exc:
            raise RuntimeError("Traccar returned invalid JSON") from exc
        if not isinstance(positions, list):
            raise RuntimeError("Traccar positions response must be a JSON array")

        envelopes = []
        for position in positions:
            if not isinstance(position, dict):
                continue
            device_id = position.get("deviceId")
            truck_id = self.device_map.get(device_id)
            if truck_id is None:
                raise ValueError(f"Traccar device {device_id!r} is not mapped in TRACCAR_DEVICE_MAP")
            recorded_at = self._timestamp(position.get("deviceTime") or position.get("serverTime"))
            external_id = str(position.get("id") or f"{device_id}-{recorded_at.isoformat()}")
            speed_kmh = float(position.get("speed", 0)) * 1.852
            ping = GpsPing(
                id=stable_id("gps", self.name, external_id),
                truck_id=truck_id,
                recorded_at=recorded_at,
                lat=float(position["latitude"]),
                lon=float(position["longitude"]),
                speed_kmh=max(0, speed_kmh),
                heading_deg=float(position["course"]) if position.get("course") is not None else None,
            )
            envelopes.append(self.wrap(ping, external_id=external_id))
        return envelopes

    @staticmethod
    def _timestamp(value: object) -> datetime:
        if not isinstance(value, str):
            raise ValueError("Traccar position has no timestamp")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Traccar timestamp must include a timezone")
        return parsed
