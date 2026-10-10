"""End-to-end smoke test of the hero loop: detect -> profile -> draft (LLM) -> approve -> sent."""

from app.seed import story


def test_health(client):
    r = client.get("/api/system/health")
    assert r.status_code == 200
    assert r.json()["now"] == "2026-10-15T07:30:00Z"


def test_llm_ping_mock(client):
    r = client.post("/api/system/llm/ping", json={"message": "hi", "language": "bg"})
    assert r.status_code == 200
    assert r.json()["llm"]["mode"] == "mock"


def test_risk_is_explainable(client):
    late = client.get(f"/api/clients/{story.LATE_PAYER}/risk").json()
    good = client.get("/api/clients/cli_0006/risk").json()
    assert late["score"] > good["score"]
    assert late["recommended_tone"] == "firm"
    codes = {f["code"] for f in late["factors"]}
    assert {"late_payment_history", "currently_overdue"} <= codes
    assert all(f["explanation"] for f in late["factors"])


def test_hero_loop(client):
    events = client.post("/api/events/scan").json()
    types = {(e["type"], e.get("shipment_id") or e.get("invoice_id")) for e in events}
    assert ("shipment_delayed", story.HERO_SHIPMENT) in types
    assert ("invoice_overdue", story.OVERDUE_INVOICE) in types

    drafts = client.get("/api/drafts", params={"status": "pending_review"}).json()
    delay = next(d for d in drafts if d["shipment_id"] == story.HERO_SHIPMENT)
    reminder = next(d for d in drafts if d["invoice_id"] == story.OVERDUE_INVOICE)
    assert delay["language"] == "en" and reminder["language"] == "bg"
    assert reminder["tone"] == "firm"
    assert "0000000801" in reminder["body"]

    # nothing can be sent without approval
    assert client.post(f"/api/drafts/{reminder['id']}/send").status_code == 409

    sent = client.post(f"/api/drafts/{reminder['id']}/approve", json={"reviewed_by": "test"}).json()
    assert sent["status"] == "sent" and sent["send_result"]["ok"]

    # scanning again does not duplicate drafts
    client.post("/api/events/scan")
    assert len(client.get("/api/drafts").json()) == len(drafts)


def test_connector_sync(client):
    r = client.post("/api/connectors/email/sync").json()
    assert r["fetched"] >= 1 and r["errors"] == []
