"""Claude provider (official Anthropic SDK). Selected with LLM_PROVIDER=anthropic. Owner: lead.

Light/fast default: LLM_MODEL=claude-haiku-4-5. Used by llm/client.py, which keeps the retry/backoff, JSON
validation, mock fallback and logging. Only the transport differs from the OpenAI-compatible path.
"""

import anthropic

from app.core.config import Settings

# the same retry policy as the OpenAI path: transient errors retry, 4xx fail fast
RETRYABLE = (anthropic.RateLimitError, anthropic.APITimeoutError, anthropic.APIConnectionError, anthropic.InternalServerError)
STATUS_ERROR = anthropic.APIStatusError


class AnthropicProvider:
    retryable = RETRYABLE
    status_error = STATUS_ERROR
    host = "api.anthropic.com"

    def __init__(self, settings: Settings):
        self.s = settings
        self._client: anthropic.Anthropic | None = None

    def _get(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic(
                api_key=self.s.llm_api_key or None,  # None -> SDK falls back to ANTHROPIC_API_KEY / `ant auth login`
                timeout=self.s.llm_timeout_seconds,
                max_retries=0,  # llm/client.py retries (with logging)
            )
        return self._client

    def complete(self, model: str, messages: list[dict]) -> str:
        """messages = [{"role": "system", ...}, user/assistant turns...] as built by LLMClient."""
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        turns = [m for m in messages if m["role"] != "system"]
        response = self._get().messages.create(
            model=model,
            max_tokens=self.s.llm_max_tokens,
            temperature=self.s.llm_temperature,
            system=system,
            messages=turns,
        )
        return "".join(block.text for block in response.content if block.type == "text")
