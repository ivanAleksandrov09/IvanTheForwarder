"""Folder watch: a file is analyzed once; failures stop after MAX_ATTEMPTS."""

import os
import time

from app.connectors import folder_watch
from app.connectors.folder_watch import ExtractedDocument, scan_once
from app.core.config import REPO_ROOT, Settings
from app.deps import get_repo
from app.schemas import LlmMeta, LlmMode


class FakeLlm:
    s = Settings(_env_file=None, llm_mode="live", llm_provider="anthropic")  # scan_once sends files to Claude
    def __init__(self, fail=False):
        self.calls, self.fail = 0, fail

    def extract_document(self, **kw):
        self.calls += 1
        if self.fail:
            raise RuntimeError("boom")
        return ExtractedDocument(doc_type="invoice", confidence=0.9, fields={"invoice_number": "123"}), LlmMeta(mode=LlmMode.live, model="m")


def _drop(folder, name, data=b"%PDF-1.4 x"):
    p = folder / name
    p.write_bytes(data)
    old = time.time() - 60
    os.utime(p, (old, old))  # past the settle window
    return p


def test_each_file_is_analyzed_once(client, tmp_path):
    folder_watch._failures.clear()
    repo, llm = get_repo(), FakeLlm()
    assert scan_once(tmp_path, repo, llm) == 0 and llm.calls == 0  # empty folder: no API call
    _drop(tmp_path, "a.pdf")
    assert scan_once(tmp_path, repo, llm) == 1 and llm.calls == 1
    assert scan_once(tmp_path, repo, llm) == 0 and llm.calls == 1  # unchanged file: not re-sent
    _drop(tmp_path, "b.pdf", b"%PDF-1.4 y")
    assert scan_once(tmp_path, repo, llm) == 1 and llm.calls == 2  # only the new file


def test_failing_file_stops_after_max_attempts(client, tmp_path):
    folder_watch._failures.clear()
    _drop(tmp_path, "bad.pdf")
    llm = FakeLlm(fail=True)
    for _ in range(folder_watch.MAX_ATTEMPTS + 3):
        scan_once(tmp_path, get_repo(), llm)
    assert llm.calls == folder_watch.MAX_ATTEMPTS


# ---- invoice due soon: event + reminder draft, once per new file ----
from datetime import timedelta  # noqa: E402

from app.core import clock  # noqa: E402
from app.schemas import InvoiceStatus  # noqa: E402


class InvoiceLlm(FakeLlm):
    def __init__(self, fields, doc_type="invoice"):
        super().__init__()
        self.fields, self.doc_type = fields, doc_type

    def extract_document(self, **kw):
        self.calls += 1
        return ExtractedDocument(doc_type=self.doc_type, confidence=0.9, fields=self.fields), LlmMeta(mode=LlmMode.live, model="m")

    def complete_json(self, **kw):  # the reminder draft is written by the (mock) client LLM
        raise AssertionError("scan must use the real LLM wrapper for drafts")


def _own_invoice(repo, days_until_due, status=InvoiceStatus.issued):
    base = repo.invoices.list(client_id="cli_0001")[0]
    inv = base.model_copy(update={"id": "inv_t0001", "number": "9999999999", "status": status,
                                  "issued_at": clock.now() - timedelta(days=20), "due_at": clock.now() + timedelta(days=days_until_due)})
    return repo.invoices.upsert(inv)


def _run(tmp_path, fields, doc_type="invoice"):
    from app.deps import get_llm

    folder_watch._failures.clear()
    folder = tmp_path / "watch"
    folder.mkdir(exist_ok=True)
    _drop(folder, "inv.pdf")
    repo, llm = get_repo(), InvoiceLlm(fields, doc_type)
    llm_for_drafts = get_llm()
    llm.complete_json = llm_for_drafts.complete_json  # drafts use the app's (mock) LLM
    scan_once(folder, repo, llm)
    return repo


def test_due_soon_invoice_makes_event_and_reminder_draft(client, tmp_path):
    repo = get_repo()
    inv = _own_invoice(repo, days_until_due=3)
    due = (clock.now() + timedelta(days=3)).date().isoformat()
    _run(tmp_path, {"invoice_number": inv.number, "due_date": due})
    events = [e for e in repo.events.list() if e.type == "invoice_due_soon"]
    assert len(events) == 1 and events[0].client_id == "cli_0001" and events[0].invoice_id == inv.id
    drafts = [d for d in repo.drafts.list() if d.invoice_id == inv.id]
    assert len(drafts) == 1 and drafts[0].kind == "payment_reminder" and events[0].draft_ids == [drafts[0].id]
    assert "overdue" not in drafts[0].body.lower() or "not overdue" in drafts[0].body.lower()
    scan_once(tmp_path / "watch", repo, InvoiceLlm({}))  # same file again: nothing new
    assert len([d for d in repo.drafts.list() if d.invoice_id == inv.id]) == 1


def test_unknown_invoice_gets_event_but_no_draft(client, tmp_path):
    repo = _run(tmp_path, {"invoice_number": "7777777777", "due_date": (clock.now() + timedelta(days=2)).date().isoformat()})
    assert len([e for e in repo.events.list() if e.type == "invoice_due_soon"]) == 1
    assert not [d for d in repo.drafts.list() if d.kind == "payment_reminder" and d.event_id]


def test_not_soon_not_invoice_or_paid_make_nothing(client, tmp_path):
    repo = get_repo()
    inv = _own_invoice(repo, days_until_due=3, status=InvoiceStatus.paid)
    soon = (clock.now() + timedelta(days=3)).date().isoformat()
    for fields, doc_type in [({"due_date": (clock.now() + timedelta(days=40)).date().isoformat()}, "invoice"),
                             ({"due_date": soon}, "cmr"),
                             ({"invoice_number": inv.number, "due_date": soon}, "invoice"),  # already paid
                             ({"due_date": "not a date"}, "invoice")]:
        for f in (tmp_path / "watch").glob("*.pdf") if (tmp_path / "watch").exists() else []:
            f.unlink()
        _run(tmp_path, fields, doc_type)
    assert not [e for e in repo.events.list() if e.type == "invoice_due_soon"]


def test_overdue_scanned_invoice_not_in_our_records_gets_event_with_client_from_name(client, tmp_path):
    repo = get_repo()
    name = repo.clients.list()[0].name
    past = (clock.now() - timedelta(days=16)).strftime("%d.%m.%Y")  # dd.mm.yyyy, as on Bulgarian invoices
    _run(tmp_path, {"invoice_number": "7777777777", "maturity_date": past, "customer_name": name, "total_amount": "960.00", "currency": "EUR"})
    events = [e for e in repo.events.list() if "7777777777" in e.title]
    assert len(events) == 1 and events[0].type == "invoice_overdue" and events[0].data["days_overdue"] == 16
    assert events[0].client_id == repo.clients.list()[0].id
    (draft,) = [d for d in repo.drafts.list() if d.event_id == events[0].id]  # drafted from the file's facts, no invoice record
    assert draft.kind == "payment_reminder" and draft.invoice_id is None and draft.client_id == events[0].client_id
    assert "7777777777" in draft.body


def test_known_overdue_invoice_is_left_to_the_overdue_detector(client, tmp_path):
    repo = get_repo()
    inv = _own_invoice(repo, days_until_due=-10)
    _run(tmp_path, {"invoice_number": inv.number, "due_date": (clock.now() - timedelta(days=10)).date().isoformat()})
    assert not [e for e in repo.events.list() if e.invoice_id == inv.id]
import os
import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.connectors import folder_watch
from app.core.config import REPO_ROOT, Settings
from app.repository import Repository
from app.risk.scoring import compute_profile
from app.schemas import Client, Language, RiskLevel

NOW = datetime(2026, 10, 15, 7, 30, tzinfo=UTC)


class _Page:
    def __init__(self, text):
        self.text = text

    def extract_text(self, **kwargs):
        return self.text


class _MockLlm:
    s = Settings(_env_file=None, llm_mode="mock")


def _client(client_id="cli_test1", name="Test Client"):
    return Client(
        id=client_id,
        name=name,
        country="BG",
        city="Sofia",
        preferred_language=Language.en,
        payment_terms_days=30,
        created_at=NOW - timedelta(days=365),
    )


def _write_pdf(folder, filename="invoice.pdf"):
    path = folder / filename
    path.write_bytes(b"searchable PDF fixture")
    old_time = time.time() - folder_watch.SETTLE_SECONDS - 1
    os.utime(path, (old_time, old_time))
    return path


def test_searchable_invoice_pdf_updates_client_risk_from_incoming_folder(tmp_path, monkeypatch):
    repo = Repository(":memory:")
    repo.clients.upsert(_client())
    _write_pdf(tmp_path)
    monkeypatch.setattr(
        folder_watch,
        "PdfReader",
        lambda _path: SimpleNamespace(
            pages=[
                _Page(
                    "INVOICE No 1234567890 Date 2026-09-01 "
                    "Total 1200.00 EUR Due 2026-09-30 Client: Test Client"
                )
            ]
        ),
    )

    assert folder_watch.scan_once(tmp_path, repo, _MockLlm()) == 1
    assert folder_watch.scan_once(tmp_path, repo, _MockLlm()) == 0

    document = repo.documents.list()[0]
    assert document.client_id == "cli_test1"
    assert document.doc_type.value == "invoice"
    profile = compute_profile("cli_test1", repo, NOW)
    overdue = next(factor for factor in profile.factors if factor.code.value == "currently_overdue")
    assert "past-due date" in overdue.explanation
    assert "EUR 1,200.00" in overdue.explanation
    assert [e.entity_id for e in overdue.evidence] == [document.id]
    assert profile.metrics.open_overdue_invoices == 0


def test_ambiguous_customer_name_does_not_affect_client_risk(tmp_path, monkeypatch):
    repo = Repository(":memory:")
    repo.clients.upsert_many([_client(), _client("cli_test2")])
    _write_pdf(tmp_path)
    monkeypatch.setattr(
        folder_watch,
        "PdfReader",
        lambda _path: SimpleNamespace(
            pages=[
                _Page(
                    "INVOICE No 1234567890 Date 2026-09-01 "
                    "Total 1200.00 EUR Due 2026-09-30 Client: Test Client"
                )
            ]
        ),
    )

    assert folder_watch.scan_once(tmp_path, repo, _MockLlm()) == 1

    assert repo.documents.list()[0].client_id is None
    profile = compute_profile("cli_test1", repo, NOW)
    assert all(factor.code.value != "currently_overdue" for factor in profile.factors)


def test_past_due_pdf_gives_client_without_invoices_a_risk_level(tmp_path, monkeypatch):
    repo = Repository(":memory:")
    repo.clients.upsert(_client())
    _write_pdf(tmp_path)
    monkeypatch.setattr(
        folder_watch,
        "PdfReader",
        lambda _path: SimpleNamespace(
            pages=[
                _Page(
                    "INVOICE No 1234567890 Date 2026-09-01 "
                    "Total 1200.00 EUR Due 2026-09-30 Client: Test Client"
                )
            ]
        ),
    )

    assert folder_watch.scan_once(tmp_path, repo, _MockLlm()) == 1

    profile = compute_profile("cli_test1", repo, NOW)
    assert profile.metrics.invoices_total == 0
    assert profile.level != RiskLevel.unknown


def test_default_watch_folder_is_docs_incoming():
    settings = Settings(_env_file=None)

    assert settings.watch_folder == REPO_ROOT / "incoming"


def test_local_invoice_extraction_handles_bulgarian_labels_and_amounts():
    fields = folder_watch._local_invoice_fields(
        "Фактура № 1234567890 Дата 01.09.2026 Общо: 1 200,00 лв. Падеж: 30.09.2026 Клиент: Тест Клиент"
    )

    assert fields == {
        "invoice_number": "1234567890",
        "issue_date": "2026-09-01",
        "due_date": "2026-09-30",
        "total_amount": "1200.00",
        "currency": "BGN",
        "client_name": "Тест Клиент",
    }
