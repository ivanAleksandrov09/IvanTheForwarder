"""Email -> client linking and email history as LLM context."""

import json
from datetime import UTC, datetime

from app.connectors.linking import link_client
from app.deps import get_llm, get_repo
from app.drafting.email_context import recent_emails
from app.schemas import Direction, Email

NOW = datetime(2026, 10, 15, tzinfo=UTC)


def _email(id_, addr, **kw):
    base = dict(id=id_, mailbox="office@vitosha-spedition.bg", direction=Direction.inbound, from_address=addr,
                to_addresses=["office@vitosha-spedition.bg"], subject="s", body_text="b", sent_at=NOW)
    return Email(**(base | kw))


def test_exact_contact_and_domain_link(client):
    repo = get_repo()
    assert link_client(_email("eml_t0001", "lmartin9886@gmail.com"), repo) == "cli_0001"  # exact contact match works even for free-mail
    assert link_client(_email("eml_t0002", "someone.else@rhein-logistik.de"), repo) == "cli_0002"  # same company domain
    assert link_client(_email("eml_t0003", "dummy@gmail.com"), repo) is None  # free-mail never matches by domain
    assert link_client(_email("eml_t0004", "x@unknown.com"), repo) is None


def test_outbound_links_by_recipient(client):
    e = _email("eml_t0005", "office@vitosha-spedition.bg", direction=Direction.outbound, to_addresses=["a.weber@rhein-logistik.de"])
    assert link_client(e, get_repo()) == "cli_0002"


def test_link_by_company_name(client):
    from app.connectors.linking import link_by_company

    repo = get_repo()
    assert link_by_company("Балкан Стил", repo) == "cli_0001"  # legal form ignored
    assert link_by_company("Rhein Logistik", repo) == "cli_0002"
    assert link_by_company("Unknown Co", repo) is None and link_by_company(None, repo) is None


def test_manual_link_survives_resync(client):
    repo = get_repo()
    repo.emails.upsert(_email("eml_t0006", "dummy@gmail.com"))
    assert client.post("/api/emails/eml_t0006/link", json={"client_id": "cli_0001"}).json()["client_id"] == "cli_0001"
    from app.connectors.ingest import _link

    again = _email("eml_t0006", "dummy@gmail.com")
    _link(again, repo)
    assert again.client_id == "cli_0001"


def test_recent_emails_only_linked_chronological_and_excludes_current(client):
    repo = get_repo()
    ctx = recent_emails(repo, "cli_0001", limit=3)
    assert 0 < len(ctx) <= 3 and [c["date"] for c in ctx] == sorted(c["date"] for c in ctx)
    assert recent_emails(repo, None) == []
    newest = max(repo.emails.list(client_id="cli_0001"), key=lambda e: e.sent_at)
    assert all(c["subject"] != newest.subject for c in recent_emails(repo, "cli_0001", exclude_id=newest.id, before=newest.sent_at)[-1:])


def test_drafting_and_extraction_prompts_contain_history(client):
    client.post("/api/drafts/generate", json={"kind": "payment_reminder", "client_id": "cli_0001"})
    email_id = next(e["id"] for e in client.get("/api/emails", params={"client_id": "cli_0001"}).json())
    client.post(f"/api/emails/{email_id}/extract")
    log = [json.loads(line) for line in (get_llm().log_path).read_text(encoding="utf-8").splitlines()]
    draft_prompt = next(r for r in log if r["task"] == "draft.payment_reminder")["messages"][1]["content"]
    extract_prompt = next(r for r in log if r["task"] == "email.extract")["messages"][1]["content"]
    assert "recent_emails" in draft_prompt and "Повторно напомняне" in draft_prompt
    assert "previous_emails" in extract_prompt and "Балкан Стил" in extract_prompt
