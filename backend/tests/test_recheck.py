"""Changing clients re-links stored invoice files and re-runs their due-date check, without re-reading any file."""

from datetime import timedelta

from app.core import clock
from app.deps import get_llm, get_repo
from app.schemas import DraftStatus
from app.events.document_checks import recheck_documents
from tests.test_folder_watch import _own_invoice, _run

PAST = lambda: (clock.now() - timedelta(days=16)).strftime("%d.%m.%Y")  # noqa: E731
CLIENT = {"name": "Brand New Co", "country": "BG", "city": "Sofia", "preferred_language": "en", "payment_terms_days": 30}


def _event_and_doc(repo):
    event = next(e for e in repo.events.list() if e.type == "invoice_overdue" and "7777777777" in e.title)
    doc = next(d for d in repo.documents.list() if d.extracted_fields.get("invoice_number") == "7777777777")
    return event, doc


def test_new_client_picks_up_files_already_read(client, tmp_path):
    repo = _run(tmp_path, {"invoice_number": "7777777777", "due_date": PAST(), "customer_name": "Brand New Co"})
    event, doc = _event_and_doc(repo)
    assert event.client_id is None and doc.client_id is None  # nobody to link it to yet

    new_id = client.post("/api/clients", json=CLIENT).json()["id"]  # background re-check runs before the response returns
    event, doc = _event_and_doc(repo)
    assert event.client_id == new_id and doc.client_id == new_id


def test_renaming_a_client_picks_up_files(client, tmp_path):
    repo = _run(tmp_path, {"invoice_number": "7777777777", "due_date": PAST(), "customer_name": "Beta Freight"})
    new_id = client.post("/api/clients", json=CLIENT | {"name": "Alpha Trading"}).json()["id"]
    assert _event_and_doc(repo)[0].client_id is None
    client.put(f"/api/clients/{new_id}", json=CLIENT | {"name": "Beta Freight"})
    assert _event_and_doc(repo)[0].client_id == new_id


def test_recheck_keeps_drafts_and_never_rereads_files(client, tmp_path, monkeypatch):
    repo = get_repo()
    inv = _own_invoice(repo, days_until_due=3)
    _run(tmp_path, {"invoice_number": inv.number, "due_date": (clock.now() + timedelta(days=3)).date().isoformat()})
    event = next(e for e in repo.events.list() if e.type == "invoice_due_soon")
    (draft_id,) = event.draft_ids
    repo.drafts.upsert(repo.drafts.require(draft_id).model_copy(update={"status": DraftStatus.rejected}))  # the operator said no

    llm = get_llm()
    monkeypatch.setattr(llm, "extract_document", lambda **kw: (_ for _ in ()).throw(AssertionError("file was re-read")))
    recheck_documents(repo, llm)
    recheck_documents(repo, llm)

    assert len([d for d in repo.drafts.list() if d.invoice_id == inv.id]) == 1  # no second draft after a rejection
    assert repo.events.require(event.id).draft_ids == [draft_id]


def test_deleting_a_client_unlinks_its_files_and_events(client, tmp_path):
    repo = _run(tmp_path, {"invoice_number": "7777777777", "due_date": PAST(), "customer_name": "Brand New Co"})
    new_id = client.post("/api/clients", json=CLIENT).json()["id"]
    assert _event_and_doc(repo)[1].client_id == new_id
    client.delete(f"/api/clients/{new_id}")
    event, doc = _event_and_doc(repo)
    assert event.client_id is None and doc.client_id is None
