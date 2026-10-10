"""Backend entrypoint: `uvicorn app.main:app --reload` (from backend/). Owner: lead."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import data, drafts, risk, system
from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError
from app.deps import get_repo, get_seed
from app.llm import LLMError
from app.repository.repo import load_seed_into

log = logging.getLogger("forwarder")


@asynccontextmanager
async def lifespan(_: FastAPI):
    s = get_settings()
    repo = get_repo()
    if s.auto_seed and repo.is_empty():
        loaded = load_seed_into(repo, get_seed())
        log.warning("Seeded empty DB %s: %s", s.resolved_db_path, loaded)
    log.warning("LLM mode=%s model=%s | clock=%s", s.llm_mode, s.llm_model, s.clock_mode)
    yield


app = FastAPI(
    title="Ivan – AI assistant for freight forwarders",
    version="0.1.0",
    lifespan=lifespan,
    separate_input_output_schemas=False,  # one TS type per model
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(NotFoundError)
def _not_found(_: Request, e: NotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(e)})


@app.exception_handler(ConflictError)
def _conflict(_: Request, e: ConflictError):
    return JSONResponse(status_code=409, content={"detail": str(e)})


@app.exception_handler(LLMError)
def _llm(_: Request, e: LLMError):
    return JSONResponse(status_code=502, content={"detail": f"LLM error: {e}"})


for r in (system.router, data.router, risk.router, drafts.router):
    app.include_router(r)
