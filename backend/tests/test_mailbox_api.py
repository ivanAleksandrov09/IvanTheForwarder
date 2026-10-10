"""Login -> sync -> extract, against a fake IMAP server."""

import imaplib

import pytest

from tests.test_connectors_imap import FakeImap, _msg


@pytest.fixture()
def fake_imap(monkeypatch):
    monkeypatch.setattr(imaplib, "IMAP4_SSL", FakeImap)
    FakeImap.login_error = None
    FakeImap.messages = {b"1": _msg("Запитване за оферта", "Търсим цена за 22 т арматура Перник – Букурещ.")}


def test_login_swaps_mock_for_imap_and_syncs(client, fake_imap):
    assert client.get("/api/connectors/email/mailbox").json()["connected"] is False
    r = client.post("/api/connectors/email/login", json={"email": "Dummy@Gmail.com", "password": "app-pass"})
    assert r.status_code == 200 and r.json()["connected"] and r.json()["provider"] == "gmail"
    assert r.json()["email"] == "dummy@gmail.com"

    sync = client.post("/api/connectors/email/sync").json()
    assert sync["connector"] == "email.imap" and sync["upserted"] == 1 and sync["errors"] == []
    assert any(e["subject"] == "Запитване за оферта" for e in client.get("/api/emails").json())


def test_bad_login_stays_on_mock_and_hides_password(client, fake_imap):
    FakeImap.login_error = "AUTHENTICATIONFAILED"
    r = client.post("/api/connectors/email/login", json={"email": "x@gmail.com", "password": "hunter2"})
    assert r.status_code == 400 and "hunter2" not in r.text
    assert client.get("/api/connectors/email/mailbox").json()["connected"] is False
    assert client.post("/api/connectors/email/sync").json()["connector"] == "email.mock"


def test_logout_restores_mock(client, fake_imap):
    client.post("/api/connectors/email/login", json={"email": "x@gmail.com", "password": "p"})
    assert client.post("/api/connectors/email/logout").json()["connected"] is False
    assert client.post("/api/connectors/email/sync").json()["connector"] == "email.mock"


def test_unknown_domain_needs_provider(client, fake_imap):
    r = client.post("/api/connectors/email/login", json={"email": "me@company.bg", "password": "p"})
    assert r.status_code == 400


def test_extract_returns_valid_schema(client):
    email_id = client.get("/api/emails").json()[0]["id"]
    r = client.post(f"/api/emails/{email_id}/extract")
    assert r.status_code == 200
    assert r.json()["intent"] in {"quote_request", "order", "payment_promise", "payment_question",
                                  "complaint", "delay_inquiry", "document", "other"}
