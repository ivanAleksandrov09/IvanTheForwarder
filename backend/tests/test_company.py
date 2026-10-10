"""Our company identity: editable in the app, kept through a demo reset, used by drafts and the system prompt."""

from app.deps import get_llm, get_repo
from app.drafting.service import _context
from app.schemas import DraftKind, GenerateDraftRequest

NEW = {"name": "Нова Спедиция ЕООД", "name_latin": "New Forwarding Ltd", "operator_name": "Петър Петров", "operator_name_latin": "Peter Petrov"}


def test_defaults_come_from_env_until_saved(client):
    assert client.get("/api/company").json()["name_latin"] == "Vitosha Forwarding Ltd"


def test_save_is_used_by_drafts_and_system_prompt_and_survives_reset(client):
    assert client.put("/api/company", json=NEW).status_code == 200
    assert {k: client.get("/api/company").json()[k] for k in NEW} == NEW
    assert get_llm().system_prompt.count("Нова Спедиция ЕООД") >= 1

    ctx, _to, _ids = _context(GenerateDraftRequest(kind=DraftKind.generic, client_id="cli_0001"), get_repo())
    assert ctx["company_name"] == NEW["name"] and ctx["company_name_latin"] == NEW["name_latin"]

    assert client.post("/api/system/reset").status_code == 200
    assert {k: client.get("/api/company").json()[k] for k in NEW} == NEW  # not wiped by reset


def test_invalid_company_is_rejected(client):
    assert client.put("/api/company", json={"name": "only name"}).status_code == 422
