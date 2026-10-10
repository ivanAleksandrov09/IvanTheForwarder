"""Real mailbox connector (IMAP). Owner: A. Enabled with CONNECTOR_EMAIL=imap.

Read-only: uses BODY.PEEK so messages are not marked as read, never deletes or moves anything.
Auth: app password (Gmail needs 2FA + app password) or an OAuth2 access token (XOAUTH2, needed by Outlook/M365).

TODO(owner A):
  - attachments -> Document (doc_type guessed from filename/content; store file under data/runtime/files/)
  - language detection (Email.language is left null for now)
  - OAuth2 flow that obtains/refreshes the access token (currently the token must be supplied)
  - link emails to clients (ingest.py), incremental sync via UIDVALIDITY/last UID
"""

import imaplib
import logging
import re
from datetime import UTC, datetime, timedelta
from email import message_from_bytes, policy
from email.message import EmailMessage
from email.utils import getaddresses, parsedate_to_datetime

from app.connectors import mailbox_store
from app.connectors.base import BaseConnector
from app.core import clock
from app.core.config import Settings
from app.core.ids import stable_id
from app.schemas import ConnectorEnvelope, ConnectorHealth, Direction, Email, SourceType

log = logging.getLogger("forwarder.imap")

MAX_MESSAGES = 50  # newest N per sync
DEFAULT_LOOKBACK_DAYS = 14
TIMEOUT_SECONDS = 20
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_TAGS = re.compile(r"<[^>]+>")


def _imap_date(dt: datetime) -> str:
    return f"{dt.day:02d}-{_MONTHS[dt.month - 1]}-{dt.year}"  # locale-independent


class ImapEmailConnector(BaseConnector):
    name = "email.imap"
    source = SourceType.email
    mode = "live"
    description = "Reads a real mailbox over IMAP (read-only)."

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

    # ---- status ----
    def health(self) -> ConnectorHealth:
        if mailbox_store.load(self.settings) is None:
            return ConnectorHealth.disabled
        return ConnectorHealth.degraded if self.last_error else ConnectorHealth.ok

    def test_login(self, creds: mailbox_store.MailboxCredentials | None = None) -> None:
        """Raises on bad credentials / unreachable server. The login prompt calls this before saving."""
        creds = creds or mailbox_store.load(self.settings)
        if creds is None:
            raise RuntimeError("no mailbox configured")
        self._connect(creds).logout()

    # ---- fetch ----
    def fetch(self, since: datetime | None = None) -> list[ConnectorEnvelope]:
        creds = mailbox_store.load(self.settings)
        if creds is None:
            raise RuntimeError("no mailbox configured: log in first or set IMAP_HOST/IMAP_USER/IMAP_PASSWORD")
        window_start = since or (clock.now() - timedelta(days=DEFAULT_LOOKBACK_DAYS))
        conn = self._connect(creds)
        try:
            conn.select("INBOX", readonly=True)
            status, data = conn.uid("SEARCH", None, "SINCE", _imap_date(window_start))
            if status != "OK":
                raise imaplib.IMAP4.error(f"SEARCH failed: {status}")
            uids = data[0].split()[-MAX_MESSAGES:]
            envelopes = []
            for uid in uids:
                status, parts = conn.uid("FETCH", uid, "(BODY.PEEK[])")
                raw = next((p[1] for p in parts if isinstance(p, tuple)), None) if status == "OK" else None
                if raw is None:
                    continue
                email = self._to_email(raw, creds.username)
                if email is None or (since is not None and email.sent_at <= since):
                    continue
                envelopes.append(self.wrap(email, external_id=email.message_id))
            return envelopes
        finally:
            try:
                conn.logout()
            except (imaplib.IMAP4.error, OSError):
                pass

    # ---- internals ----
    def _connect(self, creds: mailbox_store.MailboxCredentials) -> imaplib.IMAP4_SSL:
        conn = imaplib.IMAP4_SSL(creds.host, creds.port, timeout=TIMEOUT_SECONDS)
        if creds.auth == "xoauth2":
            token = f"user={creds.username}\x01auth=Bearer {creds.secret}\x01\x01"
            conn.authenticate("XOAUTH2", lambda _: token.encode())
        else:
            conn.login(creds.username, creds.secret)
        return conn

    @staticmethod
    def _body(msg: EmailMessage) -> str:
        part = msg.get_body(preferencelist=("plain", "html"))
        if part is None:
            return ""
        text = part.get_content()
        if part.get_content_type() == "text/html":
            text = re.sub(r"\s+\n", "\n", _TAGS.sub(" ", text))
        return text.strip()

    def _to_email(self, raw: bytes, mailbox: str) -> Email | None:
        # policy.default decodes RFC 2047 headers and charsets (utf-8, windows-1251, koi8-r, ...)
        msg: EmailMessage = message_from_bytes(raw, policy=policy.default)
        senders = [a for _, a in getaddresses([str(msg.get("From", ""))]) if "@" in a]
        if not senders:
            return None
        from_name = next((n for n, _ in getaddresses([str(msg.get("From", ""))]) if n), None)
        try:
            sent_at = parsedate_to_datetime(str(msg["Date"]))
            if sent_at.tzinfo is None:
                sent_at = sent_at.replace(tzinfo=UTC)
        except (TypeError, ValueError):
            sent_at = clock.now()
        message_id = str(msg["Message-ID"]).strip() if msg["Message-ID"] else None
        recipients = lambda h: [a for _, a in getaddresses([str(msg.get(h, ""))]) if "@" in a]  # noqa: E731
        try:
            return Email(
                # deterministic: re-syncing the same message upserts instead of duplicating
                id=stable_id("eml", mailbox, message_id or f"{senders[0]}|{sent_at.isoformat()}|{msg.get('Subject')}"),
                message_id=message_id,
                thread_id=str(msg["References"]).split()[0] if msg["References"] else None,
                mailbox=mailbox,
                direction=Direction.inbound,
                from_address=senders[0],
                from_name=from_name,
                to_addresses=recipients("To"),
                cc_addresses=recipients("Cc"),
                subject=str(msg.get("Subject", "")),
                body_text=self._body(msg),
                language=None,
                sent_at=sent_at,
            )
        except ValueError as exc:  # malformed address etc.: skip the message, never crash the sync
            log.warning("skipping unparsable message %s: %s", message_id, exc.__class__.__name__)
            return None
