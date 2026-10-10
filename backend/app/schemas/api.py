"""System / misc API payloads."""

from app.schemas.common import ContractModel, UtcDatetime
from app.schemas.drafts import LlmMeta
from app.schemas.enums import Language, LlmMode


class LlmStatus(ContractModel):
    mode: LlmMode
    model: str
    base_url_host: str
    fallback_to_mock: bool
    last_error: str | None = None


class HealthResponse(ContractModel):
    status: str  # "ok"
    app_env: str
    schema_version: str
    now: UtcDatetime  # the app clock (fixed demo time or real)
    llm: LlmStatus


class LlmPingRequest(ContractModel):
    message: str = "Представи се с едно изречение."
    language: Language | None = None


class LlmPingResponse(ContractModel):
    reply: str
    llm: LlmMeta


class ResetResponse(ContractModel):
    collections: dict[str, int]  # collection name -> rows loaded from seed
