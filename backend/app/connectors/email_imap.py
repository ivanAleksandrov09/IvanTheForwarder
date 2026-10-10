"""Real mailbox connector (IMAP). Owner: A. Enabled with CONNECTOR_EMAIL=imap.

TODO(owner A):
  - imaplib.IMAP4_SSL(settings.imap_host) -> login -> select INBOX -> search SINCE <date>
  - parse with email.message_from_bytes + email.policy.default; decode bg/ru text (UTF-8, windows-1251, koi8-r)
  - map to app.schemas.Email (id=new_id("eml"), message_id=Message-ID header, direction=inbound)
  - attachments -> Document (doc_type guessed from filename/content; store file under data/runtime/files/)
  - never log full bodies outside data/runtime/
"""

from datetime import datetime

from app.connectors.base import BaseConnector
from app.core.config import Settings
from app.schemas import ConnectorEnvelope, ConnectorHealth, SourceType


class ImapEmailConnector(BaseConnector):
    name = "email.imap"
    source = SourceType.email
    mode = "live"
    description = "Reads a real mailbox over IMAP (not implemented yet)."

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

    def health(self) -> ConnectorHealth:
        return ConnectorHealth.disabled if not self.settings.imap_host else ConnectorHealth.ok

    def fetch(self, since: datetime | None = None) -> list[ConnectorEnvelope]:
        raise NotImplementedError("TODO(owner A): IMAP connector")
