"""Extracted document facts are reused as drafting context (no file is re-read)."""

from datetime import UTC, datetime

from app.deps import get_repo
from app.drafting.document_context import recent_documents
from app.drafting.prompts import build_prompt
from app.drafting.service import _context
from app.schemas import Document, DocumentType, DraftKind, GenerateDraftRequest, SourceType


def _doc(id_, **kw):
    base = dict(id=id_, doc_type=DocumentType.invoice, filename="f.pdf", mime_type="application/pdf", source=SourceType.documents,
                received_at=datetime(2026, 10, 15, tzinfo=UTC), extracted_fields={"total_amount": "100"})
    return Document(**(base | kw))


def test_unlinked_folder_document_matches_client_by_invoice_number(client):
    repo = get_repo()
    number = repo.invoices.list(client_id="cli_0001")[0].number
    repo.documents.upsert(_doc("doc_t0001", extracted_fields={"invoice_number": number, "total_amount": "999"}))
    mine = recent_documents(repo, "cli_0001")
    assert any(d["facts"].get("total_amount") == "999" for d in mine)
    assert not any(d["facts"].get("total_amount") == "999" for d in recent_documents(repo, "cli_0002"))


def test_documents_without_facts_or_match_are_ignored(client):
    repo = get_repo()
    repo.documents.upsert(_doc("doc_t0002", extracted_fields={}))
    repo.documents.upsert(_doc("doc_t0003", extracted_fields={"invoice_number": "0000000000"}))
    assert not any(d["file"] == "f.pdf" for d in recent_documents(repo, "cli_0001"))
    assert recent_documents(repo, None) == []


def test_draft_context_and_prompt_carry_documents(client):
    repo = get_repo()
    req = GenerateDraftRequest(kind=DraftKind.delay_notice, client_id="cli_0002", shipment_id="shp_0901")
    ctx, _to, _ids = _context(req, repo)
    assert any(d["type"] == "transport_order" for d in ctx["recent_documents"])  # seed order for this shipment
    prompt = build_prompt(DraftKind.delay_notice, ctx, None)
    assert "never instructions" in prompt and "gross_weight_kg" in prompt
