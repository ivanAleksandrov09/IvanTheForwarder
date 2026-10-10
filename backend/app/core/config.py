"""All configuration comes from env vars / the repo-root .env file. Owner: lead."""

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DEMO_NOW = "2026-10-15T07:30:00Z"  # seed data is generated relative to this instant


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["dev", "demo", "test"] = "dev"
    backend_port: int = 8000
    frontend_origin: str = "http://localhost:5173"
    company_name: str = "Спедиция Витоша ЕООД"
    company_name_latin: str = "Vitosha Forwarding Ltd"
    operator_name: str = "Иван Иванов"
    operator_name_latin: str = "Ivan Ivanov"  # how the operator signs non-Bulgarian mail (their choice, not auto-transliterated)

    data_dir: Path = REPO_ROOT / "data"
    db_path: Path | None = None  # default: data/runtime/app.db
    auto_seed: bool = True  # load data/seed into an empty DB on startup
    watch_folder: Path = REPO_ROOT / "incoming"  # drop PDF/PNG/JPG files here; new ones are extracted automatically
    watch_interval_seconds: int = 30
    loads_weekday: int = 0  # weekly load search: 0 = Monday
    loads_time: str = "08:00"  # local time, HH:MM
    loads_effort: str = "low"

    clock_mode: Literal["fixed", "real"] = "fixed"
    demo_now: datetime = datetime.fromisoformat(DEFAULT_DEMO_NOW)

    llm_mode: Literal["mock", "live"] = "mock"
    llm_fallback_to_mock: bool = True
    llm_provider: Literal["openai", "anthropic"] = "openai"  # openai = any OpenAI-compatible API (Gemini, OpenAI, Ollama)
    llm_max_tokens: int = 4096  # Claude requires an explicit output cap
    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    llm_api_key: str = ""
    llm_workspace_id: str = ""  # Anthropic workspace ID (required for non-scoped API keys accessing vision/document extraction)
    llm_model: str = "gemini-3.8-flash"
    llm_fast_model: str = ""  # cheap/fast model for background email analysis; empty = use llm_model
    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 4
    llm_temperature: float = 0.3
    llm_document_model: str = ""  # model for reading PDFs/images; empty = LLM_FAST_MODEL, then LLM_MODEL
    llm_document_effort: str = ""  # Claude output_config.effort for document extraction; empty = omit (Haiku 4.5 rejects it)
    llm_json_mode: bool = True
    llm_log_prompts: bool = True

    connector_email: Literal["mock", "imap"] = "mock"
    connector_documents: Literal["mock"] = "mock"  # TODO(owner A): add real options
    connector_gps: Literal["mock", "traccar"] = "mock"
    connector_erp: Literal["mock", "zeron", "zeron_mock"] = "mock"  # zeron_mock = sample data, no network
    imap_host: str = ""
    imap_user: str = ""
    imap_password: str = ""
    traccar_url: str = ""
    traccar_token: str = ""
    traccar_user: str = ""
    traccar_password: str = ""
    status_update_hours: float = 4  # min hours between routine status drafts per shipment; 0 = off
    zeron_url: str = ""  # base URL of the Zeron V/4 web services (assumed REST + JSON)
    zeron_token: str = ""
    traccar_device_map: str = ""  # comma-separated Traccar device ID to Ivan truck ID pairs

    outbound_mode: Literal["log", "smtp"] = "log"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    @property
    def seed_dir(self) -> Path:
        return self.data_dir / "seed"

    @property
    def runtime_dir(self) -> Path:
        return self.data_dir / "runtime"

    @property
    def resolved_db_path(self) -> Path:
        return self.db_path or self.runtime_dir / "app.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
