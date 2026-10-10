"""Polls the connected mailbox every minute and analyzes new mail in the background. Also pulls live GPS and drafts status updates. Owner: A."""

import asyncio
import logging

from app.connectors import mailbox_store
from app.connectors.email_imap import ImapEmailConnector
from app.connectors.ingest import sync
from app.connectors.insights import process_new_emails
from app.core.config import get_settings
from app.deps import get_connectors, get_llm, get_repo
from app.drafting.status_updates import draft_status_updates
from app.schemas import SourceType

log = logging.getLogger("forwarder.autosync")
INTERVAL_SECONDS = 60


def tick() -> None:
    connector = get_connectors().get(SourceType.email)
    creds = mailbox_store.load(get_settings())
    if isinstance(connector, ImapEmailConnector) and creds is not None:
        repo = get_repo()
        sync(connector, repo)
        process_new_emails(repo, get_llm(), creds.username)

    erp_connector = get_connectors().get(SourceType.erp)  # clients, trucks, loads, invoices (+ positions) from the ERP
    if erp_connector is not None:
        sync(erp_connector, get_repo())

    # Also pull live GPS and draft status updates
    gps_connector = get_connectors().get(SourceType.gps)
    if gps_connector is not None:
        repo = get_repo()
        sync(gps_connector, repo)
        draft_status_updates(repo, get_llm())


async def autosync_loop(first_delay: float = 5, interval: float = INTERVAL_SECONDS) -> None:
    await asyncio.sleep(first_delay)
    while True:
        try:
            await asyncio.to_thread(tick)
        except Exception as exc:  # never let the loop die
            log.warning("autosync failed: %s", type(exc).__name__)
        await asyncio.sleep(interval)
