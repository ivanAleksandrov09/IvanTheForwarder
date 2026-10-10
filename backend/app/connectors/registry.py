"""Chooses the active connector per source from config. Owner: A."""

from app.connectors import mailbox_store
from app.connectors.base import BaseConnector
from app.connectors.email_imap import ImapEmailConnector
from app.connectors.email_mock import MockEmailConnector
from app.connectors.gps_traccar import TraccarGpsConnector
from app.core.config import Settings
from app.repository import SeedStore
from app.schemas import SourceType


def use_imap(connectors: dict[SourceType, BaseConnector], settings: Settings) -> ImapEmailConnector:
    """Swap the active email connector to IMAP at runtime (login prompt)."""
    connector = ImapEmailConnector(settings)
    connectors[SourceType.email] = connector
    return connector


def use_mock_email(connectors: dict[SourceType, BaseConnector], seed: SeedStore) -> None:
    connectors[SourceType.email] = MockEmailConnector(seed)


def build_connectors(settings: Settings, seed: SeedStore) -> dict[SourceType, BaseConnector]:
    connectors: list[BaseConnector] = []

    use_imap_email = settings.connector_email == "imap" or mailbox_store.is_saved(settings)  # saved login survives restarts
    connectors.append(ImapEmailConnector(settings) if use_imap_email else MockEmailConnector(seed))
    if settings.connector_gps == "traccar":
        connectors.append(TraccarGpsConnector(settings))
    # TODO(owner A): documents (mock: feeds/documents_inbox.json; real: watched folder + OCR/vision)
    # TODO(owner A): erp (mock: feeds/erp_*.json; real: ERP export/CSV/API)
    # STRETCH(owner A): call_log, erp_screenshot (vision), external_web (speditor.net -> scrape or mock)

    return {c.source: c for c in connectors}
