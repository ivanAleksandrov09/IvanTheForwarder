"""REFERENCE CONNECTOR - copy this pattern for documents/gps/erp. Owner: A.

Delivers the emails in data/seed/feeds/email_inbox.json as if they just arrived in the mailbox.
"""

from datetime import datetime

from app.connectors.base import BaseConnector
from app.repository import SeedStore
from app.schemas import ConnectorEnvelope, Email, SourceType


class MockEmailConnector(BaseConnector):
    name = "email.mock"
    source = SourceType.email
    mode = "mock"
    description = "Replays data/seed/feeds/email_inbox.json as newly received mail."

    def __init__(self, seed: SeedStore):
        super().__init__()
        self.seed = seed

    def fetch(self, since: datetime | None = None) -> list[ConnectorEnvelope]:
        emails = self.seed.load_feed("email_inbox", Email)  # schema-validated on load (see seed_store.FEED_MODELS)
        if since is not None:
            emails = [e for e in emails if e.sent_at > since]
        return [self.wrap(e, external_id=e.message_id) for e in emails]
