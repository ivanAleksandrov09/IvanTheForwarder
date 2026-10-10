"""IMAP connector against a fake server (no network)."""

import imaplib
from datetime import UTC, datetime
from email.message import EmailMessage

import pytest

from app.connectors import mailbox_store
from app.connectors.email_imap import ImapEmailConnector
from app.core.config import Settings
from app.schemas import ConnectorEnvelope, ConnectorHealth, Email


def _msg(subject, body, sender="Георги Петров <g.petrov@balkansteel.bg>", date="Wed, 14 Oct 2026 09:00:00 +0300",
         message_id="<a1@balkansteel.bg>", charset="utf-8", subtype="plain") -> bytes:
    m = EmailMessage()
    m["From"], m["To"], m["Subject"], m["Date"] = sender, "office@vitosha-spedition.bg", subject, date
    if message_id:
        m["Message-ID"] = message_id
    m.set_content(body, subtype=subtype, charset=charset, cte="8bit" if charset != "utf-8" else None)
    return m.as_bytes()


class FakeImap:
    """Stands in for imaplib.IMAP4_SSL. Class attributes configure the mailbox."""

    messages: dict[bytes, bytes] = {}
    login_error: str | None = None
    calls: list = []

    def __init__(self, host, port=993, timeout=None):
        FakeImap.calls = [("connect", host, port)]

    def login(self, user, password):
        if self.login_error:
            raise imaplib.IMAP4.error(self.login_error)
        FakeImap.calls.append(("login", user))

    def authenticate(self, mech, cb):
        FakeImap.calls.append(("authenticate", mech, cb(None)))

    def select(self, box, readonly=False):
        FakeImap.calls.append(("select", box, readonly))
        return "OK", [b"1"]

    def uid(self, cmd, *args):
        if cmd == "SEARCH":
            return "OK", [b" ".join(self.messages)]
        FakeImap.calls.append(("fetch", args[1]))  # must be BODY.PEEK so nothing is marked read
        return "OK", [(b"1 (UID 1 BODY[] {1}", self.messages[args[0]]), b")"]

    def logout(self):
        return "BYE", []


@pytest.fixture()
def connector(tmp_path, monkeypatch):
    monkeypatch.setattr(imaplib, "IMAP4_SSL", FakeImap)
    FakeImap.login_error = None
    FakeImap.messages = {}
    monkeypatch.setattr(Settings, "runtime_dir", property(lambda self: tmp_path))
    settings = Settings(imap_host="", imap_user="", imap_password="")
    mailbox_store.save(settings, mailbox_store.MailboxCredentials.for_provider("office@gmail.com", "app-pass"))
    return ImapEmailConnector(settings)


def test_fetch_maps_to_valid_envelopes(connector):
    FakeImap.messages = {
        b"1": _msg("Нов товар Перник – Букурещ", "Здравейте, имаме 22 т арматура."),
        b"2": _msg("Нова оферта", "Цена до утре?", charset="windows-1251", message_id="<a2@balkansteel.bg>"),
        b"3": _msg("HTML only", "<p>Hello <b>there</b></p>", subtype="html", message_id="<a3@x.com>", sender="a@x.com"),
    }
    envs = connector.fetch()
    assert len(envs) == 3 and all(isinstance(e, ConnectorEnvelope) for e in envs)
    emails = {e.payload.message_id: e.payload for e in envs}
    assert all(isinstance(e, Email) for e in emails.values())
    first = emails["<a1@balkansteel.bg>"]
    assert first.subject == "Нов товар Перник – Букурещ" and first.from_name == "Георги Петров"
    assert first.sent_at == datetime(2026, 10, 14, 6, 0, tzinfo=UTC)  # +03:00 -> UTC
    assert "арматура" in first.body_text
    assert "Цена до утре" in emails["<a2@balkansteel.bg>"].body_text  # windows-1251 decoded
    assert "<p>" not in emails["<a3@x.com>"].body_text and "there" in emails["<a3@x.com>"].body_text


def test_read_only(connector):
    FakeImap.messages = {b"1": _msg("x", "y")}
    connector.fetch()
    assert ("select", "INBOX", True) in FakeImap.calls
    assert ("fetch", "(BODY.PEEK[])") in FakeImap.calls


def test_ids_are_stable_across_syncs(connector):
    FakeImap.messages = {b"1": _msg("x", "y")}
    assert connector.fetch()[0].payload.id == connector.fetch()[0].payload.id


def test_skips_bad_messages_without_crashing(connector):
    FakeImap.messages = {b"1": _msg("no sender", "y", sender="undisclosed-recipients:;"), b"2": _msg("ok", "y", message_id="<ok@x.com>")}
    assert [e.payload.subject for e in connector.fetch()] == ["ok"]


def test_since_filters_old_messages(connector):
    FakeImap.messages = {b"1": _msg("old", "y")}
    assert connector.fetch(since=datetime(2026, 10, 15, tzinfo=UTC)) == []


def test_bad_password_raises_on_login_test(connector):
    FakeImap.login_error = "AUTHENTICATIONFAILED"
    with pytest.raises(imaplib.IMAP4.error):
        connector.test_login()


def test_xoauth2_uses_bearer_token(tmp_path, monkeypatch):
    monkeypatch.setattr(imaplib, "IMAP4_SSL", FakeImap)
    FakeImap.messages = {}
    monkeypatch.setattr(Settings, "runtime_dir", property(lambda self: tmp_path))
    settings = Settings(imap_host="", imap_user="", imap_password="")
    mailbox_store.save(settings, mailbox_store.MailboxCredentials.for_provider("me@outlook.com", "tok123", auth="xoauth2"))
    ImapEmailConnector(settings).fetch()
    auth = next(c for c in FakeImap.calls if c[0] == "authenticate")
    assert auth[1] == "XOAUTH2" and b"auth=Bearer tok123" in auth[2]


def test_provider_detected_from_email_domain():
    assert mailbox_store.MailboxCredentials.for_provider("a@gmail.com", "x").host == "imap.gmail.com"
    assert mailbox_store.MailboxCredentials.for_provider("a@hotmail.com", "x").host == "outlook.office365.com"


def test_health_disabled_without_credentials(tmp_path, monkeypatch):
    monkeypatch.setattr(Settings, "runtime_dir", property(lambda self: tmp_path))
    c = ImapEmailConnector(Settings(imap_host="", imap_user="", imap_password=""))
    assert c.health() == ConnectorHealth.disabled
