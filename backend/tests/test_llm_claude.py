"""Claude provider (LLM_PROVIDER=anthropic) against a fake Anthropic client."""

from types import SimpleNamespace

import anthropic
import pytest

from app.core.config import Settings
from app.llm import LLMClient
from app.schemas import EmailExtraction


class FakeAnthropic:
    calls: list[dict] = []
    reply = '{"intent": "quote_request", "summary": "Quote for steel"}'
    error: Exception | None = None

    def __init__(self, **kw):
        FakeAnthropic.init = kw
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        FakeAnthropic.calls.append(kw)
        if FakeAnthropic.error:
            raise FakeAnthropic.error
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=FakeAnthropic.reply)])


@pytest.fixture()
def claude(tmp_path, monkeypatch):
    monkeypatch.setattr(anthropic, "Anthropic", FakeAnthropic)
    monkeypatch.setattr(Settings, "runtime_dir", property(lambda self: tmp_path))
    FakeAnthropic.calls, FakeAnthropic.error = [], None
    FakeAnthropic.reply = '{"intent": "quote_request", "summary": "Quote for steel"}'

    def make(**kw):
        return LLMClient(Settings(llm_mode="live", llm_provider="anthropic", llm_api_key="k", llm_model="claude-haiku-4-5",
                                  llm_fallback_to_mock=False, llm_max_retries=0, **kw))
    return make


def test_json_call_goes_through_claude(claude):
    llm = claude()
    result, meta = llm.complete_json(task="email.extract", prompt="Email: please quote steel", schema=EmailExtraction)
    assert result.intent == "quote_request" and meta.model == "claude-haiku-4-5" and meta.mode == "live"
    call = FakeAnthropic.calls[0]
    assert call["model"] == "claude-haiku-4-5" and call["max_tokens"] == 4096
    assert "Ivan" in call["system"]  # system prompt sent as the top-level `system`
    assert [m["role"] for m in call["messages"]] == ["user"]
    assert llm.status().base_url_host == "api.anthropic.com"


def test_json_in_code_fence_and_repair_flow(claude):
    FakeAnthropic.reply = '```json\n{"intent": "other", "summary": "x"}\n```'
    result, _ = claude().complete_json(task="t", prompt="p", schema=EmailExtraction)
    assert result.intent == "other"


def test_fast_model_override(claude):
    llm = claude(llm_fast_model="claude-haiku-4-5")
    llm.complete_json(task="t", prompt="p", schema=EmailExtraction, fast=True)
    assert FakeAnthropic.calls[0]["model"] == "claude-haiku-4-5"


def test_connection_error_falls_back_to_mock_when_enabled(claude):
    import httpx2

    FakeAnthropic.error = anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com"))
    llm = LLMClient(Settings(llm_mode="live", llm_provider="anthropic", llm_api_key="k", llm_fallback_to_mock=True, llm_max_retries=0))
    _, meta = llm.complete_text(task="system.ping", prompt="hi", mock_context={"language": "en"})
    assert meta.used_fallback and "APIConnectionError" in (llm.last_error or "")
