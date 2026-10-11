"""Finds open truck loads on the web with Claude's web search tool, weekly and on demand. Owner: B."""

import asyncio
import hashlib
import json
import logging
from datetime import date, datetime, timedelta

import anthropic
import httpx
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.schemas.common import ContractModel

log = logging.getLogger("forwarder.loads")

PROMPT = (
    "You help a Bulgarian road freight forwarder find cargo it can take. "
    "Search the web for up to 5 example road freight loads (full truck or part load) advertised on any freight exchange, "
    "load board or forwarder cargo page, loading anywhere in Bulgaria, Romania, Greece, Serbia or Turkey, going to anywhere in Europe. "
    "Recent postings are preferred, but older ones are acceptable if that is all you can find. "
    "Only include an offer if you found it on a specific page; never invent a URL, price or date. "
    "Use null for any value the page does not show. "
    "Answer with ONLY a JSON array of up to 5 objects, no prose, with keys: "
    "origin ('City, CC'), destination ('City, CC'), pickup_date (YYYY-MM-DD or null), cargo, weight_kg (integer or null), "
    "vehicle (tent, mega, box or flatbed, or null), price_eur (integer or null), source (site name), source_url (full https URL). "
    "If you find fewer than 5, return what you found; return [] only if you found none at all."
)
OFFER_FIELDS = ("origin", "destination", "pickup_date", "cargo", "weight_kg", "vehicle", "price_eur", "source", "source_url")
MAX_PAUSES = 3  # server-side search loops; more than this means something is wrong


class LoadOffer(ContractModel):
    id: str
    origin: str
    destination: str
    pickup_date: date | None = None
    cargo: str | None = None
    weight_kg: int | None = None
    vehicle: str | None = None
    price_eur: int | None = None
    source: str
    source_url: str
    verified: bool = False  # True when the source URL answered with a non-error status


def _offers_file(s: Settings):
    return s.runtime_dir / "loads.json"


def read_offers() -> list[LoadOffer]:
    path = _offers_file(get_settings())
    if not path.exists():
        return []
    return [LoadOffer.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))]


def _create(client: anthropic.Anthropic, s: Settings, messages: list, extra_body: dict | None):
    return client.messages.create(
        model=s.llm_fast_model or s.llm_model,
        max_tokens=s.llm_max_tokens,
        tools=[{"type": "web_search_20260209", "name": "web_search", "allowed_callers": ["direct"]}],
        messages=messages,
        **({"extra_body": extra_body} if extra_body else {}),
    )


def _ask_claude(s: Settings) -> list:
    client = anthropic.Anthropic(
        api_key=s.llm_api_key,
        timeout=120,
        max_retries=2,
        default_headers={"anthropic-workspace-id": s.llm_workspace_id} if s.llm_workspace_id else None,
    )
    prompt = f"{PROMPT} Today is {date.today().isoformat()}."
    messages: list = [{"role": "user", "content": prompt}]
    extra_body = {"output_config": {"effort": s.loads_effort}} if s.loads_effort else None
    for _ in range(MAX_PAUSES):
        try:
            response = _create(client, s, messages, extra_body)
        except anthropic.BadRequestError as exc:
            if extra_body is None or "effort" not in str(exc):
                raise
            extra_body = None  # this model has no effort setting (e.g. Haiku 4.5): search without it
            response = _create(client, s, messages, extra_body)
        if response.stop_reason != "pause_turn":
            break
        messages = [*messages, {"role": "assistant", "content": response.content}]
    text = "".join(block.text for block in response.content if block.type == "text")
    start, end = text.find("["), text.rfind("]") + 1
    if start < 0 or end <= start:
        log.warning("load search: no JSON array in Claude's answer, treating it as no offers: %s", text[:200])
        return []
    return json.loads(text[start:end])


def _reachable(url: str) -> bool:
    try:
        response = httpx.get(url, follow_redirects=True, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    except httpx.HTTPError:
        return False
    return response.status_code < 400


def search_loads(s: Settings) -> list[LoadOffer]:
    if not s.llm_api_key:
        raise RuntimeError("LLM_API_KEY is not set")
    items: list = []
    for _ in range(3):  # Claude sometimes answers with an empty list; ask again before giving up
        try:
            items = _ask_claude(s)
        except anthropic.APIError as exc:  # auth, workspace, quota, tool not enabled...: report it instead of a bare 500
            raise RuntimeError(f"Claude request failed: {getattr(exc, 'message', exc)}") from exc
        if items:
            break
    offers: list[LoadOffer] = []
    seen: set[str] = set()
    for item in items:
        url = item.get("source_url") if isinstance(item, dict) else None
        if not isinstance(url, str):
            continue
        # Several offers can come from one listing page, so the id covers the route and date, not just the URL.
        key = "|".join(str(item.get(k)) for k in ("source_url", "origin", "destination", "pickup_date", "cargo"))
        offer_id = f"ld_{hashlib.sha1(key.encode()).hexdigest()[:12]}"
        if offer_id in seen:
            continue
        seen.add(offer_id)
        try:
            offers.append(
                LoadOffer(
                    id=offer_id,
                    verified=_reachable(url),
                    **{k: item.get(k) for k in OFFER_FIELDS},
                )
            )
        except ValidationError as exc:
            log.warning("dropped malformed load offer from %s: %s", url, exc.errors()[0]["msg"])
    return offers


def refresh_loads(s: Settings | None = None) -> list[LoadOffer]:
    s = s or get_settings()
    offers = search_loads(s)
    path = _offers_file(s)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([o.model_dump(mode="json") for o in offers], ensure_ascii=False, indent=2), encoding="utf-8")
    log.warning("load search stored %d offers", len(offers))
    return offers


def next_run(now: datetime, weekday: int, hhmm: str) -> datetime:
    hour, minute = (int(part) for part in hhmm.split(":"))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    target += timedelta(days=(weekday - now.weekday()) % 7)
    return target if target > now else target + timedelta(days=7)


async def loads_weekly_loop() -> None:
    s = get_settings()
    if not s.llm_api_key:
        log.warning("weekly load search off: LLM_API_KEY is not set")
        return
    while True:
        now = datetime.now().astimezone()
        target = next_run(now, s.loads_weekday, s.loads_time)
        log.warning("next weekly load search at %s", target.isoformat())
        await asyncio.sleep((target - now).total_seconds())
        try:
            await asyncio.to_thread(refresh_loads, s)
        except Exception as exc:  # never let the loop die
            log.warning("weekly load search failed: %s", type(exc).__name__)
