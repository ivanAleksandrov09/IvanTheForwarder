"""Opt-in sharing of the capacity profile: aggregates only, consent first, withdrawable."""

import json

import httpx

from app.core.config import get_settings
from app.deps import get_repo


def _published_files():
    return list((get_settings().runtime_dir / "network").glob("*.json"))


def test_preview_is_aggregates_only_and_contains_no_business_secrets(client):
    state = client.get("/api/network/profile").json()
    preview = state["preview"]
    repo = get_repo()
    own = [t for t in repo.trucks.list() if t.is_own_fleet]
    assert preview["fleet"]["trucks"] == len(own) and preview["fleet"]["max_capacity_kg"] == max(t.capacity_kg for t in own)
    assert preview["max_load_kg"] == preview["fleet"]["max_capacity_kg"]  # derived while the company leaves it blank
    assert preview["lanes"] and all(lane["shipments"] >= 3 for lane in preview["lanes"])  # small lanes are suppressed
    assert preview["contact_email"] is None  # contact is opt-in
    blob = json.dumps(preview, ensure_ascii=False)
    secrets = [c.name for c in repo.clients.list()] + [t.plate_number for t in repo.trucks.list()] + [i.number for i in repo.invoices.list()]
    secrets += [c.contacts[0].email for c in repo.clients.list() if c.contacts and c.contacts[0].email]
    assert not [s for s in secrets if s and s in blob]


def test_company_choices_override_derived_values_and_contact_is_opt_in(client):
    body = {"consent": False, "share_contact": True, "home_region": "Sofia, Bulgaria", "countries_served": ["BG", "RO"], "max_load_kg": 18000,
            "trailer_types": ["tent"], "cargo_types": ["general", "steel"], "adr": True, "languages": ["bg", "en"],
            "public_notes": "Own fleet, 24/7 dispatch", "contact_email": "Dispatch@Example.bg", "contact_phone": "+359888123456"}
    preview = client.put("/api/network/profile", json=body).json()["preview"]
    assert preview["home_region"] == "Sofia, Bulgaria" and preview["countries_served"] == ["BG", "RO"] and preview["max_load_kg"] == 18000
    assert preview["trailer_types"] == ["tent"] and preview["adr"] is True and preview["contact_email"] == "dispatch@example.bg"
    off = client.put("/api/network/profile", json=body | {"share_contact": False}).json()["preview"]
    assert off["contact_email"] is None and off["contact_phone"] is None


def test_nothing_is_published_without_consent(client):
    assert client.post("/api/network/publish").status_code == 409
    assert _published_files() == []


def test_publish_with_consent_writes_the_previewed_profile_and_withdraw_removes_it(client):
    client.put("/api/network/profile", json={"consent": True, "home_region": "Sofia"})
    state = client.post("/api/network/publish").json()
    assert state["settings"]["last_published_at"] and "published" in state["settings"]["last_publish_status"]
    (path,) = _published_files()
    sent = json.loads(path.read_text(encoding="utf-8"))
    assert sent["company_uid"] == state["settings"]["company_uid"] and sent["home_region"] == "Sofia"
    assert {k: sent[k] for k in ("fleet", "lanes", "max_load_kg")} == {k: state["preview"][k] for k in ("fleet", "lanes", "max_load_kg")}

    after = client.post("/api/network/withdraw").json()
    assert after["settings"]["consent"] is False and "withdrawn" in after["settings"]["last_publish_status"]
    assert _published_files() == []
    assert client.post("/api/network/publish").status_code == 409  # consent is gone


def test_company_uid_is_stable_and_settings_survive_reset(client):
    uid = client.get("/api/network/profile").json()["settings"]["company_uid"]
    client.put("/api/network/profile", json={"consent": True, "home_region": "Plovdiv"})
    assert client.put("/api/network/profile", json={"consent": True, "home_region": "Plovdiv 2"}).json()["settings"]["company_uid"] == uid
    assert client.post("/api/system/reset").status_code == 200
    kept = client.get("/api/network/profile").json()["settings"]
    assert kept["company_uid"] == uid and kept["home_region"] == "Plovdiv 2" and kept["consent"] is True


def test_central_server_requests_and_failures(client, monkeypatch):
    calls = []

    def fake(method):
        def call(url, **kw):
            calls.append((method, url, kw.get("headers"), kw.get("json")))
            return httpx.Response(200, request=httpx.Request(method, url))
        return call

    monkeypatch.setattr(httpx, "put", fake("PUT"))
    monkeypatch.setattr(httpx, "delete", fake("DELETE"))
    monkeypatch.setattr(get_settings(), "network_url", "https://central.example/")
    monkeypatch.setattr(get_settings(), "network_token", "tok")
    client.put("/api/network/profile", json={"consent": True})
    uid = client.post("/api/network/publish").json()["settings"]["company_uid"]
    method, url, headers, body = calls[0]
    assert (method, url) == ("PUT", f"https://central.example/api/v1/companies/{uid}") and headers == {"Authorization": "Bearer tok"}
    assert body["company_uid"] == uid and "clients" not in body and "invoices" not in body
    client.post("/api/network/withdraw")
    assert calls[1][:2] == ("DELETE", f"https://central.example/api/v1/companies/{uid}")

    def boom(url, **kw):
        raise httpx.ConnectError("down", request=httpx.Request("PUT", url))

    monkeypatch.setattr(httpx, "put", boom)
    client.put("/api/network/profile", json={"consent": True})
    r = client.post("/api/network/publish")
    assert r.status_code == 502
    assert client.get("/api/network/profile").json()["settings"]["last_publish_status"].startswith("failed:")
