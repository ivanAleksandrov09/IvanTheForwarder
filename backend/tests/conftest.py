import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Fresh app with a temp DB, mock LLM, log sender. Seed auto-loads on startup."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("LLM_MODE", "mock")
    monkeypatch.setenv("OUTBOUND_MODE", "log")
    monkeypatch.setenv("CLOCK_MODE", "fixed")
    monkeypatch.setenv("AUTO_SEED", "true")  # tests still run on the mock seed data (open question: see chat)
    monkeypatch.setenv("CONNECTOR_EMAIL", "mock")
    monkeypatch.setenv("CONNECTOR_GPS", "mock")
    monkeypatch.setenv("WATCH_FOLDER", str(tmp_path / "incoming"))  # never read the real incoming/ folder in tests
    from app.core import config
    from app.deps import reset_singletons

    reset_singletons()
    monkeypatch.setattr(config.Settings, "runtime_dir", property(lambda self: tmp_path / "runtime"))
    from app.main import app

    with TestClient(app) as c:
        yield c
    reset_singletons()
