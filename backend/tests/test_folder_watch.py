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

    def extract_text(self):
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

    assert settings.watch_folder == REPO_ROOT / "docs" / "incoming"


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
