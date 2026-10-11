"""Background analysis of new emails: LLM extracts facts, identifies the client, result is stored. Owner: A.

Runs after every sync of a real mailbox (and from the autosync loop). Nobody clicks anything.
Failed or fallback-to-mock results are NOT stored, so they are retried (max MAX_FAILURES times per process).
"""

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from app.connectors.linking import link_by_company
from app.core import clock
from app.drafting.email_context import recent_emails
from app.llm import LLMClient
from app.repository import Repository
from app.schemas import Direction, EmailExtraction, EmailInsight, LlmMode

log = logging.getLogger("forwarder.insights")

WORKERS = 4
MAX_FAILURES = 3
BODY_CHARS = 2500  # enough for an inquiry; keeps the call fast and cheap

_lock = threading.Lock()
_failures: dict[str, int] = {}


def _prompt(repo: Repository, email) -> tuple[str, dict]:
    client = repo.clients.get(email.client_id) if email.client_id else None
    ctx = {"subject": email.subject, "body": email.body_text[:BODY_CHARS]}
    context = {
        "from": email.from_address,
        "from_name": email.from_name,
        **ctx,
        "client_name": client.name if client else None,
        "previous_emails": recent_emails(repo, email.client_id, exclude_id=email.id, before=email.sent_at, limit=3),
    }
    prompt = (
        "TASK: Extract structured facts from the email in CONTEXT (subject/body). Use null for anything not stated in "
        "THIS email; never guess. `company_name` is the sender's company from the signature or body. "
        "`previous_emails` is background only: use it to understand references like \"the same load\", "
        "never copy facts from it. Dates as YYYY-MM-DD.\nCONTEXT:\n" + json.dumps(context, ensure_ascii=False)
    )
    return prompt, ctx


def analyze_email(email_id: str, repo: Repository, llm: LLMClient) -> EmailInsight | None:
    """Extract, store and (if still unlinked) link by the company name found. None = no real LLM answer.
    The mock LLM never produces stored insights: its answers are canned text, not facts from the email."""
    if llm.s.llm_mode != "live":
        return None
    email = repo.emails.require(email_id)
    prompt, ctx = _prompt(repo, email)
    extraction, meta = llm.complete_json(
        task="email.extract", prompt=prompt, schema=EmailExtraction, mock_context=ctx, fast=True
    )
    if meta.used_fallback or meta.mode != LlmMode.live:
        return None
    insight = repo.email_insights.upsert(
        EmailInsight(email_id=email_id, extracted_at=clock.now(), extraction=extraction, model=meta.model)
    )
    current = repo.emails.get(email_id)
    if current is not None and current.client_id is None:
        client_id = link_by_company(extraction.company_name, repo)
        if client_id:
            repo.emails.upsert(current.model_copy(update={"client_id": client_id}))
    return insight


def process_new_emails(repo: Repository, llm: LLMClient, mailbox: str) -> int:
    """Analyze inbound emails of `mailbox` that have no insight yet. Returns how many were analyzed."""
    if llm.s.llm_mode != "live":  # no real LLM: nothing to analyze, and nothing mock is stored
        return 0
    if not _lock.acquire(blocking=False):  # another run is in progress
        return 0
    try:
        todo = sorted(
            (e for e in repo.emails.list(mailbox=mailbox)
             if e.direction == Direction.inbound and _failures.get(e.id, 0) < MAX_FAILURES
             and repo.email_insights.get(e.id) is None),
            key=lambda e: e.sent_at,
            reverse=True,  # newest first
        )

        def work(email_id: str) -> bool:
            try:
                if analyze_email(email_id, repo, llm) is not None:
                    return True
            except Exception as exc:  # one bad email must not stop the rest
                log.warning("analysis failed for %s: %s", email_id, type(exc).__name__)
            _failures[email_id] = _failures.get(email_id, 0) + 1
            return False

        with ThreadPoolExecutor(WORKERS) as pool:
            return sum(pool.map(work, [e.id for e in todo]))
    finally:
        _lock.release()
