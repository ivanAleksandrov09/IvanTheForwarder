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

    clock_mode: Literal["fixed", "real"] = "fixed"
    demo_now: datetime = datetime.fromisoformat(DEFAULT_DEMO_NOW)

    llm_mode: Literal["mock", "live"] = "mock"
    llm_fallback_to_mock: bool = True
    llm_provider: Literal["openai", "anthropic"] = "openai"  # openai = any OpenAI-compatible API (Gemini, OpenAI, Ollama)
    llm_max_tokens: int = 4096  # Claude requires an explicit output cap
    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    llm_api_key: str = ""
    llm_model: str = "gemini-3.8-flash"
    llm_fast_model: str = ""  # cheap/fast model for background email analysis; empty = use llm_model
    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 4
    llm_temperature: float = 0.3
    llm_json_mode: bool = True
    llm_log_prompts: bool = True

    connector_email: Literal["mock", "imap"] = "mock"
    connector_documents: Literal["mock"] = "mock"  # TODO(owner A): add real options
    connector_gps: Literal["mock"] = "mock"
    connector_erp: Literal["mock"] = "mock"
    imap_host: str = ""
    imap_user: str = ""
    imap_password: str = ""

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
