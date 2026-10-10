"""The ONLY way any module talks to an LLM. Owner: lead.

OpenAI-compatible Chat Completions API, so provider = config:
  Gemini : LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/  LLM_MODEL=gemini-2.5-flash
  OpenAI : LLM_BASE_URL=https://api.openai.com/v1                                  LLM_MODEL=gpt-4o-mini
  Ollama : LLM_BASE_URL=http://localhost:11434/v1                                  LLM_MODEL=qwen2.5:7b-instruct

Features: mock mode, retry with exponential backoff (+Retry-After), timeout, JSON-schema validation
with one repair round-trip, fallback to canned responses, JSONL prompt/response log.

Usage:
    text, meta = llm.complete_text(task="system.ping", prompt="...", mock_context={...})
    obj,  meta = llm.complete_json(task="draft.payment_reminder", prompt="...", schema=DraftContent, mock_context={...})
"""

import base64
import json
import random
import re
import time
import uuid
from datetime import UTC, datetime
from typing import TypeVar
from urllib.parse import urlparse

import openai
from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.llm.mock_responses import mock_response
from app.llm.system_prompt import build_system_prompt
from app.schemas import LlmMeta, LlmMode, LlmStatus

T = TypeVar("T", bound=BaseModel)

_RETRYABLE = (openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError, openai.InternalServerError)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, settings: Settings):
        self.s = settings
        self._client: openai.OpenAI | None = None
        self._claude = None
        if settings.llm_provider == "anthropic":  # imported lazily: OpenAI-only setups don't need the SDK
            from app.llm.anthropic_provider import AnthropicProvider

            self._claude = AnthropicProvider(settings)
        self.last_error: str | None = None
        self.system_prompt = build_system_prompt(settings.company_name, settings.operator_name)
        self.log_path = settings.runtime_dir / "logs" / "llm.jsonl"

    # ------------------------------------------------------------------ public API
    def status(self) -> LlmStatus:
        return LlmStatus(
            mode=LlmMode(self.s.llm_mode),
            model=self.s.llm_model if self.s.llm_mode == "live" else "mock",
            base_url_host=self._host(),
            fallback_to_mock=self.s.llm_fallback_to_mock,
            last_error=self.last_error,
        )

    def complete_text(
        self, *, task: str, prompt: str, mock_context: dict | None = None, system_extra: str | None = None,
        fast: bool = False,
    ) -> tuple[str, LlmMeta]:
        messages = self._messages(prompt, system_extra)
        return self._run(task, messages, json_mode=False, mock_context=mock_context, model=self._model(fast))

    def complete_json(
        self,
        *,
        task: str,
        prompt: str,
        schema: type[T],
        mock_context: dict | None = None,
        system_extra: str | None = None,
        fast: bool = False,
    ) -> tuple[T, LlmMeta]:
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        prompt = f"{prompt}\n\nReturn ONLY one JSON object matching this JSON Schema:\n{schema_json}"
        messages = self._messages(prompt, system_extra)
        model = self._model(fast)
        text, meta = self._run(task, messages, json_mode=True, mock_context=mock_context, model=model)
        try:
            return self._parse(text, schema), meta
        except (ValueError, ValidationError) as e:
            if meta.mode == LlmMode.mock:
                raise LLMError(f"canned response for {task!r} does not match {schema.__name__}: {e}") from e
            first_error = str(e)[:1000]
        # one repair round-trip
        messages += [
            {"role": "assistant", "content": text},
            {"role": "user", "content": f"Invalid output: {first_error}. Return ONLY the corrected JSON object."},
        ]
        text, meta = self._run(task + ".repair", messages, json_mode=True, mock_context=mock_context, model=model)
        try:
            return self._parse(text, schema), meta
        except (ValueError, ValidationError) as e:
            if self.s.llm_fallback_to_mock:
                text, meta = self._mock(task, messages, mock_context, used_fallback=True)
                return self._parse(text, schema), meta
            raise LLMError(f"LLM returned invalid JSON for {task!r}: {e}") from e

    def extract_document(
        self, *, task: str, data: bytes, mime_type: str, prompt: str, schema: type[T]
    ) -> tuple[T, LlmMeta]:
        """Reads a PDF or image with Claude (LLM_PROVIDER=anthropic). Raises LLMError on failure, no mock fallback."""
        if self._claude is None:
            raise LLMError("document extraction needs LLM_PROVIDER=anthropic")
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        source = {"type": "base64", "media_type": mime_type, "data": base64.b64encode(data).decode("ascii")}
        file_block = {"type": "document", "source": source} if mime_type == "application/pdf" else {"type": "image", "source": source}
        content = [file_block, {"type": "text", "text": f"{prompt}\n\nReturn ONLY one JSON object matching this JSON Schema:\n{schema_json}"}]
        messages = [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": content}]
        text, meta = self._live(task, messages, json_mode=False, model=self.s.llm_document_model or self._model(fast=True), effort=self.s.llm_document_effort or None)
        return self._parse(text, schema), meta

    # ------------------------------------------------------------------ internals
    def _messages(self, prompt: str, system_extra: str | None) -> list[dict]:
        system = self.system_prompt + (f"\n{system_extra}" if system_extra else "")
        return [{"role": "system", "content": system}, {"role": "user", "content": prompt}]

    @staticmethod
    def _parse(text: str, schema: type[T]) -> T:
        cleaned = _FENCE.sub("", text.strip()).strip()
        return schema.model_validate(json.loads(cleaned))

    def _openai(self) -> openai.OpenAI:
        if self._client is None:
            self._client = openai.OpenAI(
                base_url=self.s.llm_base_url,
                api_key=self.s.llm_api_key or "not-set",
                timeout=self.s.llm_timeout_seconds,
                max_retries=0,  # we retry ourselves (with logging)
            )
        return self._client

    def _host(self) -> str:
        return self._claude.host if self._claude else urlparse(self.s.llm_base_url).netloc

    def _model(self, fast: bool) -> str:
        """fast=True uses LLM_FAST_MODEL (same provider/key) for background extraction; empty = main model."""
        return (self.s.llm_fast_model if fast else "") or self.s.llm_model

    def _run(self, task: str, messages: list[dict], json_mode: bool, mock_context: dict | None, model: str | None = None):
        if self.s.llm_mode == "mock":
            return self._mock(task, messages, mock_context, used_fallback=False)
        try:
            return self._live(task, messages, json_mode, model or self.s.llm_model)
        except LLMError:
            if self.s.llm_fallback_to_mock:
                return self._mock(task, messages, mock_context, used_fallback=True)
            raise

    def _live(self, task: str, messages: list[dict], json_mode: bool, model: str, effort: str | None = None) -> tuple[str, LlmMeta]:
        kwargs: dict = {"model": model, "messages": messages, "temperature": self.s.llm_temperature}
        if json_mode and self.s.llm_json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if self._claude:  # Claude has no JSON mode: the prompt carries the schema and the reply is validated below
            retryable, status_error = self._claude.retryable, self._claude.status_error
            call = lambda: self._claude.complete(model, messages, effort)  # noqa: E731
        else:
            retryable, status_error = _RETRYABLE, openai.APIStatusError
            call = lambda: self._openai().chat.completions.create(**kwargs).choices[0].message.content or ""  # noqa: E731
        attempt = 0
        while True:
            started = time.perf_counter()
            try:
                text = call()
                latency = int((time.perf_counter() - started) * 1000)
                log_id = self._log(task, messages, text, mode="live", latency_ms=latency, error=None, model=model)
                self.last_error = None
                return text, LlmMeta(mode=LlmMode.live, model=model, log_id=log_id, latency_ms=latency)
            except retryable as e:
                attempt += 1
                self.last_error = f"{type(e).__name__}: {e}"
                self._log(task, messages, None, mode="live", latency_ms=None, error=self.last_error, model=model)
                if attempt > self.s.llm_max_retries:
                    raise LLMError(f"{task}: gave up after {attempt} attempts: {self.last_error}") from e
                time.sleep(self._backoff(attempt, e))
            except status_error as e:  # 400/401/403/404: retrying won't help
                self.last_error = f"{type(e).__name__} {e.status_code}: {e.message}"
                self._log(task, messages, None, mode="live", latency_ms=None, error=self.last_error, model=model)
                raise LLMError(f"{task}: {self.last_error}") from e

    @staticmethod
    def _backoff(attempt: int, e: Exception) -> float:
        retry_after = None
        response = getattr(e, "response", None)
        if response is not None:
            try:
                retry_after = float(response.headers.get("retry-after", ""))
            except ValueError:
                pass
        base = retry_after if retry_after is not None else min(2**attempt, 20)
        return base + random.uniform(0, 0.5)

    def _mock(self, task: str, messages: list[dict], ctx: dict | None, used_fallback: bool):
        text = mock_response(task.removesuffix(".repair"), ctx)
        log_id = self._log(task, messages, text, mode="mock", latency_ms=0, error=None, fallback=used_fallback)
        return text, LlmMeta(mode=LlmMode.mock, model="mock", used_fallback=used_fallback, log_id=log_id, latency_ms=0)

    def _log(self, task, messages, response, *, mode, latency_ms, error, fallback=False, model=None) -> str | None:
        if not self.s.llm_log_prompts:
            return None
        log_id = uuid.uuid4().hex[:12]
        record = {
            "log_id": log_id,
            "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),  # wall clock on purpose (real call time)
            "task": task,
            "mode": mode,
            "fallback": fallback,
            "model": (model or self.s.llm_model) if mode == "live" else "mock",
            "base_url_host": self._host(),
            "latency_ms": latency_ms,
            "error": error,
            "messages": messages,
            "response": response,
        }
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return log_id
