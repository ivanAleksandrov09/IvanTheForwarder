"""Writes connector output to the repository. The only path from a connector into the DB. Owner: A."""

from app.connectors.base import BaseConnector
from app.connectors.linking import link_client
from app.core import clock
from app.repository import Repository
from app.schemas import Email, PayloadType, SyncResult


def _link(email: Email, repo: Repository) -> None:
    """Keep an existing (possibly manual) link; otherwise auto-link by address."""
    if email.client_id is not None:
        return
    existing = repo.emails.get(email.id)
    email.client_id = (existing.client_id if existing else None) or link_client(email, repo)


def sync(connector: BaseConnector, repo: Repository) -> SyncResult:
    started = clock.now()
    errors: list[str] = []
    upserted = 0
    envelopes = []
    try:
        envelopes = connector.fetch(since=None)  # TODO(owner A): pass connector.last_sync_at for incremental sync
        for env in envelopes:
            # TODO(owner A): dedupe by env.external_id (Message-ID) when the source has no stable ids
            # TODO(owner A): emit DomainEvent(email_received / document_received) for new items
            if env.payload_type == PayloadType.email:
                _link(env.payload, repo)
            repo.collection_for_payload(env.payload_type).upsert(env.payload)
            upserted += 1
        connector.last_error = None
    except Exception as e:  # a broken connector must never take down the app
        connector.last_error = f"{type(e).__name__}: {e}"
        errors.append(connector.last_error)
    connector.last_sync_at = clock.now()
    return SyncResult(
        source=connector.source,
        connector=connector.name,
        fetched=len(envelopes),
        upserted=upserted,
        errors=errors,
        started_at=started,
        finished_at=clock.now(),
    )
