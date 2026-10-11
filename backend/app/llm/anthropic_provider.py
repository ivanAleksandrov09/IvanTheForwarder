"""Claude provider using the official Anthropic SDK."""

import anthropic

from app.core.config import Settings

# transient errors retry, 4xx errors fail fast
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
                default_headers={"anthropic-workspace-id": self.s.llm_workspace_id} if self.s.llm_workspace_id else None,
            )
        return self._client

    def complete(self, model: str, messages: list[dict], effort: str | None = None) -> str:
        """messages = [{"role": "system", ...}, user/assistant turns...] as built by LLMClient."""
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        turns = [m for m in messages if m["role"] != "system"]
        response = self._get().messages.create(
            model=model,
            max_tokens=self.s.llm_max_tokens,
            system=system,
            messages=turns,
            extra_body={"output_config": {"effort": effort}} if effort else None,
        )
        return "".join(block.text for block in response.content if block.type == "text")
