"""Central index settings (env vars / repo-root .env). Separate from the company app's settings. Owner: lead."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class CentralSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    # dev default matches docker-compose.yml (host port 5434; 5432 is usually taken by a local Postgres)
    central_database_url: str = "postgresql://central:central@localhost:5434/central"
    # Bearer token companies use to publish/withdraw. Empty = publishing is disabled (503), never open.
    central_ingest_token: str = ""


@lru_cache
def get_settings() -> CentralSettings:
    return CentralSettings()
