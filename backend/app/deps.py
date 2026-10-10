"""Process-wide singletons, injected into routes with FastAPI Depends(). Owner: lead.
Tests reset them with reset_singletons() after changing env vars.
"""

from functools import lru_cache

from app.core.config import get_settings
from app.llm import LLMClient
from app.repository import Repository, SeedStore


@lru_cache
def get_repo() -> Repository:
    return Repository(get_settings().resolved_db_path)


@lru_cache
def get_seed() -> SeedStore:
    return SeedStore(get_settings().seed_dir)


@lru_cache
def get_llm() -> LLMClient:
    return LLMClient(get_settings())


@lru_cache
def get_connectors():
    from app.connectors.registry import build_connectors

    return build_connectors(get_settings(), get_seed())


def reset_singletons() -> None:
    for f in (get_settings, get_repo, get_seed, get_llm, get_connectors):
        f.cache_clear()
