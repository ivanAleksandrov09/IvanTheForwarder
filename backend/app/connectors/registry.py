"""Chooses the active connector per source from config. Owner: A."""

from app.connectors.base import BaseConnector
from app.connectors.email_imap import ImapEmailConnector
from app.connectors.email_mock import MockEmailConnector
from app.core.config import Settings
from app.repository import SeedStore
from app.schemas import SourceType


def build_connectors(settings: Settings, seed: SeedStore) -> dict[SourceType, BaseConnector]:
    connectors: list[BaseConnector] = []

    connectors.append(MockEmailConnector(seed) if settings.connector_email == "mock" else ImapEmailConnector(settings))

    # TODO(owner A): documents (mock: feeds/documents_inbox.json; real: watched folder + OCR/vision)
    # TODO(owner A): gps (mock: feeds/gps_live.json replaying pings; real: telematics API e.g. Wialon/GPS Bulgaria)
    # TODO(owner A): erp (mock: feeds/erp_*.json; real: ERP export/CSV/API)
    # STRETCH(owner A): call_log, erp_screenshot (vision), external_web (speditor.net -> scrape or mock)

    return {c.source: c for c in connectors}
