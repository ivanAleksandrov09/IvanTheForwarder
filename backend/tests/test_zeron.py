"""Zeron V/4 connector (assumed API) against the sample data, and the account summary it feeds to drafts."""

import httpx

from app.connectors.ingest import sync
from app.connectors.registry import build_connectors
from app.connectors.zeron import ZeronConnector
from app.core.config import Settings, get_settings
from app.deps import get_repo, get_seed
from app.drafting.prompts import build_prompt
from app.drafting.service import _context
from app.schemas import DraftKind, GenerateDraftRequest, SourceType


def _connector(**kw):
    return ZeronConnector(get_settings(), get_repo, mock=True, **kw)


def _counts(repo):
    return {n: repo.collection(n).count() for n in ("clients", "trucks", "shipments", "invoices", "gps_pings")}


def test_sync_maps_zeron_data_and_matches_known_records(client):
    repo, before = get_repo(), _counts(get_repo())
    conn = _connector()
    result = sync(conn, repo)
    after = _counts(repo)
    assert result.errors == [] and conn.skipped == []
    # clients matched by VAT (2 known) are not duplicated; the unknown counterparty is created
    assert after["clients"] == before["clients"] + 1
    lohmann = next(c for c in repo.clients.list() if c.vat_number == "DE262896804")
    assert lohmann.name.startswith("Lohmann") and lohmann.contacts[0].email.endswith(".example")
    # trucks matched by plate (2 known) are not duplicated; the new one is created
    assert after["trucks"] == before["trucks"] + 1
    truck = next(t for t in repo.trucks.list() if t.label == "Truck 7")
    assert after["shipments"] == before["shipments"] + 3 and after["invoices"] == before["invoices"] + 4
    assert after["gps_pings"] == before["gps_pings"] + 3
    # relations survive the mapping
    load = next(s for s in repo.shipments.list() if s.reference == "SPD-2026-1150")
    assert load.client_id == lohmann.id and load.truck_id == truck.id and load.status.value == "in_transit"
    inv = next(i for i in repo.invoices.list() if i.number == "0000013902")
    assert inv.client_id == lohmann.id and inv.total.amount_minor == 96000 and inv.shipment_ids == [load.id]
    balkan = next(i for i in repo.invoices.list() if i.number == "0000013901")
    assert balkan.client_id == "cli_0001" and balkan.vat.amount_minor == 20000


def test_sample_requests_and_incremental_sync(client):
    repo, conn = get_repo(), _connector()
    sync(conn, repo)
    assert conn.api.requests == [
        "GET /api/v1/counterparties",
        "GET /api/v1/vehicles",
        "GET /api/v1/orders",
        "GET /api/v1/invoices",
        "GET /api/v1/vehicles/positions",
    ]
    counts = _counts(repo)
    again = sync(conn, repo)  # only rows modified since the last sync are requested
    assert again.fetched == 0 and _counts(repo) == counts
    assert conn.api.requests[-1].startswith("GET /api/v1/vehicles/positions?modifiedSince=")


def test_known_clients_are_never_overwritten(client):
    repo = get_repo()
    cli = repo.clients.require("cli_0001")
    repo.clients.upsert(cli.model_copy(update={"name": "Edited by the operator"}))
    sync(_connector(), repo)
    assert repo.clients.require("cli_0001").name == "Edited by the operator"


def test_invalid_row_is_skipped_not_fatal(client):
    repo, conn = get_repo(), _connector()
    conn.api._answer_mock("invoices", None)  # loads the sample file
    conn.api._data["invoices"][0]["number"] = "not-a-number"
    result = sync(conn, repo)
    assert result.errors == [] and len(conn.skipped) == 1 and "INV-9001" in conn.skipped[0]
    assert len([i for i in repo.invoices.list() if i.number.startswith("00000139")]) == 3


def test_registry_builds_zeron_mock_from_config(client):
    connectors = build_connectors(Settings(connector_erp="zeron_mock"), get_seed())
    erp = connectors[SourceType.erp]
    assert erp.name == "erp.zeron" and erp.mode == "mock" and erp.info().health.value == "ok"
    assert SourceType.erp not in build_connectors(Settings(connector_erp="mock"), get_seed())


def test_live_mode_sends_bearer_requests_to_zeron_url(client, monkeypatch):
    seen = []

    def fake_get(url, params=None, headers=None, timeout=None):
        seen.append((url, params, headers))
        return httpx.Response(200, json={"items": []}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    conn = ZeronConnector(Settings(connector_erp="zeron", zeron_url="https://zeron.example/", zeron_token="secret"), get_repo)
    assert conn.mode == "live" and conn.fetch() == []
    assert seen[0][0] == "https://zeron.example/api/v1/counterparties" and seen[0][2]["Authorization"] == "Bearer secret"
    assert [u.rsplit("/api/v1", 1)[1] for u, _, _ in seen] == ["/counterparties", "/vehicles", "/orders", "/invoices", "/vehicles/positions"]
    assert ZeronConnector(Settings(connector_erp="zeron"), get_repo).info().health.value == "disabled"


def test_account_summary_reaches_the_draft_context_and_prompt(client):
    repo = get_repo()
    sync(_connector(), repo)
    lohmann = next(c for c in repo.clients.list() if c.vat_number == "DE262896804")
    ctx, _to, _ids = _context(GenerateDraftRequest(kind=DraftKind.generic, client_id=lohmann.id), repo)
    standing = ctx["account_summary"]
    assert standing["open_invoices"]["count"] == 2 and standing["open_invoices"]["overdue_count"] == 1
    (load,) = standing["active_loads"]
    assert load["reference"] == "SPD-2026-1150" and load["route"] == "София → Versmold" and load["truck"] == "СВ 2045 КН"
    prompt = build_prompt(DraftKind.generic, ctx, None)
    assert "account_summary" in prompt and "never invent numbers" in prompt
    assert "margin" not in str(standing).lower() and "cost" not in standing["active_loads"][0]
