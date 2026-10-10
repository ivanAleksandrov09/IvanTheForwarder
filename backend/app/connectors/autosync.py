"""Polls the connected mailbox every minute and analyzes new mail in the background. Owner: A."""

import asyncio
import logging

from app.connectors import mailbox_store
from app.connectors.email_imap import ImapEmailConnector
from app.connectors.ingest import sync
from app.connectors.insights import process_new_emails
from app.core.config import get_settings
from app.deps import get_connectors, get_llm, get_repo
from app.schemas import SourceType

log = logging.getLogger("forwarder.autosync")
INTERVAL_SECONDS = 60


def tick() -> None:
    connector = get_connectors().get(SourceType.email)
    creds = mailbox_store.load(get_settings())
    if not isinstance(connector, ImapEmailConnector) or creds is None:
        return
    repo = get_repo()
    sync(connector, repo)
    process_new_emails(repo, get_llm(), creds.username)


async def autosync_loop(first_delay: float = 5, interval: float = INTERVAL_SECONDS) -> None:
    await asyncio.sleep(first_delay)
    while True:
        try:
            await asyncio.to_thread(tick)
        except Exception as exc:  # never let the loop die
            log.warning("autosync failed: %s", type(exc).__name__)
        await asyncio.sleep(interval)
