"""Previous correspondence of a client, as LLM context. Used by drafting and email extraction."""

from datetime import datetime

from app.repository import Repository

BODY_CHARS = 500


def recent_emails(repo: Repository, client_id: str | None, exclude_id: str | None = None,
                  before: datetime | None = None, limit: int = 5) -> list[dict]:
    """Last `limit` emails linked to the client (oldest first). Linked = business-relevant; unlinked mail is never included."""
    if client_id is None:
        return []
    items = [e for e in repo.emails.list(client_id=client_id)
             if e.id != exclude_id and e.body_text.strip() and (before is None or e.sent_at < before)]
    items.sort(key=lambda e: e.sent_at)
    return [
        {"date": e.sent_at.strftime("%Y-%m-%d"), "direction": e.direction.value, "subject": e.subject,
         "body": e.body_text.strip()[:BODY_CHARS]}
        for e in items[-limit:]
    ]
