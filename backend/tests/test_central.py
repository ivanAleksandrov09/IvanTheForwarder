"""Central index against a real Postgres (pgserver, embedded and isolated): publish, withdraw, search, the public page, and the
full round trip from the company app."""

from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from fastapi.testclient import TestClient

pgserver = pytest.importorskip("pgserver")

from app.schemas.network import FleetSummary, LaneStat, PublicCompanyProfile  # noqa: E402

TOKEN = "test-ingest-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
NOW = datetime(2026, 10, 15, 8, 0, tzinfo=UTC)


@pytest.fixture(scope="session")
def pg_url(tmp_path_factory):
    server = pgserver.get_server(tmp_path_factory.mktemp("pgdata"))
    yield server.get_uri()


@pytest.fixture()
def central(pg_url, monkeypatch):
    monkeypatch.setenv("CENTRAL_DATABASE_URL", pg_url)
    monkeypatch.setenv("CENTRAL_INGEST_TOKEN", TOKEN)
    from central import config

    config.get_settings.cache_clear()
    from central.main import app

    with TestClient(app) as c:
        with psycopg.connect(pg_url, autocommit=True) as conn:
            conn.execute("TRUNCATE companies")
        yield c
    config.get_settings.cache_clear()


def profile(uid, **kw):
    base = dict(company_uid=uid, name="Alpha Trans", name_latin="Alpha Trans", home_region="Sofia, Bulgaria", countries_served=["BG", "DE"],
                lanes=[LaneStat(from_country="BG", to_country="DE", shipments=5)],
                fleet=FleetSummary(trucks=10, trailer_types=["tent"], max_capacity_kg=24000), max_load_kg=24000, trailer_types=["tent"],
                cargo_types=["general"], adr=False, languages=["bg", "en"], public_notes="", updated_at=NOW)
    return PublicCompanyProfile(**(base | kw)).model_dump(mode="json")


def put(central, p, headers=AUTH):
    return central.put(f"/api/v1/companies/{p['company_uid']}", json=p, headers=headers)


@pytest.fixture()
def seeded(central):
    docs = [
        profile("alpha000001", name="Alpha Trans", countries_served=["BG", "RO", "DE"], trailer_types=["tent", "reefer"], cargo_types=["general", "food", "pharma"],
                public_notes="Temperature controlled pharma transport", fleet=FleetSummary(trucks=12, trailer_types=["tent", "reefer"], max_capacity_kg=24000)),
        profile("bravo000002", name="Bravo Steel Haulage", home_region="Plovdiv, Bulgaria", countries_served=["BG", "TR"], trailer_types=["flatbed"],
                cargo_types=["steel", "oversized"], max_load_kg=25000, adr=True, languages=["bg", "tr"], public_notes="Heavy and oversized steel",
                lanes=[LaneStat(from_country="BG", to_country="TR", shipments=4)], contact_email="dispatch@bravo.example", contact_phone="+359888111222",
                fleet=FleetSummary(trucks=8, trailer_types=["flatbed"], max_capacity_kg=25000)),
        profile("charlie00003", name="Charlie Logistik GmbH", home_region="Köln, Germany", countries_served=["DE", "NL"], max_load_kg=12000, languages=["en"],
                lanes=[LaneStat(from_country="DE", to_country="NL", shipments=9)], fleet=FleetSummary(trucks=3, trailer_types=["tent"], max_capacity_kg=12000)),
    ]
    for d in docs:
        assert put(central, d).status_code == 204
    return docs


def names(central, **params):
    r = central.get("/api/v1/search", params=params)
    assert r.status_code == 200, r.text
    return sorted(i["profile"]["name"].split()[0] for i in r.json()["items"])


# ---- publishing and withdrawing
def test_ingest_requires_the_token(central, monkeypatch):
    p = profile("alpha000001")
    assert central.put("/api/v1/companies/alpha000001", json=p).status_code == 401
    assert put(central, p, headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert central.delete("/api/v1/companies/alpha000001").status_code == 401
    monkeypatch.setenv("CENTRAL_INGEST_TOKEN", "")
    from central import config

    config.get_settings.cache_clear()
    assert put(central, p).status_code == 503  # no token configured = publishing is off, never open


def test_invalid_publications_are_rejected(central):
    p = profile("alpha000001")
    assert central.put("/api/v1/companies/bravo000002", json=p, headers=AUTH).status_code == 422  # uid mismatch
    assert put(central, p | {"schema_version": 2}).status_code == 422
    assert central.put("/api/v1/companies/short", json=profile("short"), headers=AUTH).status_code == 422
    assert put(central, p | {"max_load_kg": "heavy"}).status_code == 422


def test_publish_is_an_idempotent_upsert_and_stale_updates_are_ignored(central):
    p = profile("alpha000001")
    put(central, p)
    put(central, p)
    assert central.get("/api/v1/search").json()["total"] == 1
    put(central, p | {"name": "Alpha Renamed", "updated_at": (NOW + timedelta(hours=1)).isoformat()})
    put(central, p | {"name": "Old Name", "updated_at": (NOW - timedelta(hours=1)).isoformat()})  # arrives late
    assert central.get("/api/v1/companies/alpha000001").json()["name"] == "Alpha Renamed"


def test_withdraw_deletes_the_row(central, seeded, pg_url):
    assert central.delete("/api/v1/companies/bravo000002", headers=AUTH).status_code == 204
    assert central.delete("/api/v1/companies/bravo000002", headers=AUTH).status_code == 204  # idempotent
    assert central.get("/api/v1/companies/bravo000002").status_code == 404
    with psycopg.connect(pg_url) as conn:
        assert conn.execute("SELECT count(*) FROM companies WHERE company_uid = 'bravo000002'").fetchone()[0] == 0


# ---- search
def test_structured_filters(central, seeded):
    assert names(central) == ["Alpha", "Bravo", "Charlie"]
    assert names(central, country=["BG"]) == ["Alpha", "Bravo"]
    assert names(central, country=["BG", "DE"]) == ["Alpha"]  # must serve ALL
    assert names(central, country=["BG", "NL"]) == []
    assert names(central, lane=["BG-DE"]) == ["Alpha"] and names(central, lane=["BG-TR"]) == ["Bravo"]
    assert names(central, lane=["BG-DE", "BG-TR"]) == []
    assert names(central, trailer=["flatbed"]) == ["Bravo"] and names(central, trailer=["tent", "flatbed"]) == ["Alpha", "Bravo", "Charlie"]
    assert names(central, cargo=["general", "food"]) == ["Alpha"] and names(central, cargo=["steel"]) == ["Bravo"]
    assert names(central, min_load_kg=24500) == ["Bravo"] and names(central, min_load_kg=30000) == []
    assert names(central, adr="true") == ["Bravo"]
    assert names(central, language=["tr"]) == ["Bravo"] and names(central, language=["en"]) == ["Alpha", "Charlie"]
    assert names(central, region="plovdiv") == ["Bravo"]  # case-insensitive substring
    assert names(central, country=["BG"], trailer=["tent"], min_load_kg=20000) == ["Alpha"]  # combined


def test_free_text_search_ranks_and_handles_unicode_and_odd_input(central, seeded):
    assert names(central, q="pharma") == ["Alpha"]
    assert names(central, q="oversized steel") == ["Bravo"]
    assert names(central, q="Köln") == ["Charlie"]
    top = central.get("/api/v1/search", params={"q": "steel"}).json()["items"][0]
    assert top["profile"]["name"].startswith("Bravo") and top["rank"] > 0
    for odd in ["'\"&|!:*()", "a OR", "-", "\\", "%_"]:
        assert central.get("/api/v1/search", params={"q": odd}).status_code == 200


def test_cyrillic_names_are_searchable(central):
    put(central, profile("vitosha0001", name="Спедиция Витоша ЕООД", name_latin="Vitosha Forwarding Ltd"))
    assert names(central, q="Витоша") == ["Спедиция"] and names(central, q="vitosha") == ["Спедиция"]


def test_default_order_is_largest_fleet_first_and_pagination(central, seeded):
    page = central.get("/api/v1/search", params={"limit": 1}).json()
    assert page["total"] == 3 and len(page["items"]) == 1 and page["items"][0]["profile"]["name"].startswith("Alpha")
    assert central.get("/api/v1/search", params={"limit": 1, "offset": 2}).json()["items"][0]["profile"]["name"].startswith("Charlie")


def test_user_input_cannot_reach_the_sql_text(central, seeded):
    evil = "'; DROP TABLE companies; --"
    for params in ({"region": evil}, {"q": evil}, {"region": "%"}):
        assert central.get("/api/v1/search", params=params).status_code == 200
    assert central.get("/api/v1/search", params={"region": "%"}).json()["total"] == 0  # % is literal, not a wildcard
    assert central.get("/api/v1/search").json()["total"] == 3  # table intact


def test_bad_parameters_are_rejected(central):
    for params in ({"country": "bulgaria"}, {"lane": "BG_DE"}, {"limit": 500}, {"trailer": "spaceship"}, {"min_load_kg": -1}, {"language": "xx"}):
        assert central.get("/api/v1/search", params=params).status_code == 422, params


def test_contact_is_only_visible_when_the_company_shared_it(central, seeded):
    by_name = {i["profile"]["name"].split()[0]: i["profile"] for i in central.get("/api/v1/search").json()["items"]}
    assert by_name["Bravo"]["contact_email"] == "dispatch@bravo.example"
    assert by_name["Alpha"]["contact_email"] is None and by_name["Alpha"]["contact_phone"] is None


# ---- the page outsiders see
def test_public_page_is_served_with_safe_headers_and_no_inline_script(central):
    page = central.get("/")
    assert page.status_code == 200 and "text/html" in page.headers["content-type"]
    assert "default-src 'self'" in page.headers["content-security-policy"] and page.headers["x-content-type-options"] == "nosniff"
    assert '<script src="/static/app.js">' in page.text and "<script>" not in page.text
    js = central.get("/static/app.js").text
    assert "textContent" in js and "innerHTML" not in js  # company-written text is never inserted as HTML


# ---- the whole path: company app -> central index -> outsiders -> withdraw
def test_company_app_publishes_and_withdraws_through_the_central_index(client, central, monkeypatch):
    import httpx

    from app.core.config import get_settings as company_settings

    base = "http://central.test"
    monkeypatch.setattr(company_settings(), "network_url", base)
    monkeypatch.setattr(company_settings(), "network_token", TOKEN)

    def forward(method):
        def call(url, **kw):
            args = {"headers": kw.get("headers")} | ({"json": kw["json"]} if "json" in kw else {})
            return getattr(central, method)(url.removeprefix(base), **args)
        return call

    monkeypatch.setattr(httpx, "put", forward("put"))
    monkeypatch.setattr(httpx, "delete", forward("delete"))

    client.put("/api/network/profile", json={"consent": True, "home_region": "Sofia", "contact_email": "ops@example.bg", "share_contact": False})
    uid = client.post("/api/network/publish").json()["settings"]["company_uid"]
    found = central.get("/api/v1/search", params={"region": "Sofia"}).json()
    assert found["total"] == 1 and found["items"][0]["profile"]["company_uid"] == uid
    assert found["items"][0]["profile"]["contact_email"] is None  # contact was not shared, so it never left the company
    assert found["items"][0]["profile"]["fleet"]["trucks"] > 0

    client.post("/api/network/withdraw")
    assert central.get("/api/v1/search").json()["total"] == 0
    assert central.get(f"/api/v1/companies/{uid}").status_code == 404
