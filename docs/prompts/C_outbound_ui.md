# Prompt for Person C — Notifications, outbound & frontend (paste into Claude Code, opened in the repo root)

```text
You are my pair programmer at a 24-hour hackathon. I am Person C on a 5-person team.

## Project
"Ivan" is a self-hostable AI assistant for small Bulgarian freight forwarders (спедитори, Sofia). It gathers data
(email, documents, GPS, ERP), profiles clients with explainable risk, detects events, and PREPARES outgoing
communication (emails, messages, invoices, CMRs) as items in a "ready to send" queue. NOTHING is sent without explicit
human approval. Everything runs on deterministic MOCK data. Monorepo: FastAPI + Pydantic v2 + SQLite backend
(backend/app), React 19 + Vite + TypeScript frontend (frontend/). Start with `npm run dev` (UI on :5173, API on :8000).

## My responsibility
Drafting via the LLM wrapper, the approval queue, confirm-and-send, AND the whole product UI (this is the demo surface).

## Files I own (work ONLY here)
backend/app/drafting/** · backend/app/outbound/** · backend/app/api/drafts.py · draft entries in
backend/app/llm/mock_responses.py · frontend/** (except the generated frontend/src/api/schema.ts) ·
backend/tests/test_drafts*.py · my README section.
Do NOT edit backend/app/schemas/** (lead only), llm/client.py, llm/system_prompt.py (propose changes to the lead), or
other owners' folders. Need a field/enum? STOP and write a short schema change request for team chat. Never hand-write
TS types; after schema changes run `npm run gen:types` and import from frontend/src/api/types.ts.

## Contracts (already in the repo, read them first)
- schemas/drafts.py: DraftMessage{id drf_, kind payment_reminder|delay_notice|quote_reply|invoice|cmr|generic, channel
  email|sms|viber|document, status pending_review|approved|rejected|sent|failed, language, tone, client/shipment/invoice/event
  ids, to/cc, subject, body, attachment_document_ids, rationale, timestamps, reviewed_by/at, rejection_reason, sent_at,
  send_result: SendResult, llm: LlmMeta{mode, model, used_fallback, log_id, latency_ms}}.
  DraftContent{subject, body, language, tone, rationale} = the JSON the LLM must return.
  GenerateDraftRequest, UpdateDraftRequest (PATCH: null = unchanged), ApproveDraftRequest, RejectDraftRequest.
- LLM: from app.deps get_llm(); llm.complete_json(task="draft.<kind>", prompt=..., schema=DraftContent, mock_context=ctx)
  returns (obj, LlmMeta). It handles retries, timeout, JSON validation + repair, fallback to canned mock, and logging.
  Never import the provider SDK directly. The system prompt already enforces: drafts only, facts only from CONTEXT (placeholders like
  [ДАТА]/[REASON] otherwise), never reveal risk scores to clients, bg formal Вие and bg number/date formats.
- drafting/service.py builds CONTEXT from the repository + B's get_profile() (recommended_tone) → prompt (drafting/prompts.py) → LLM → DraftMessage.
- drafting/proactive.py: HIGH events → drafts (EVENT_TO_DRAFT).
- outbound/queue.py: state machine; send_draft() REFUSES anything not human-approved (keep this invariant + its test).
  outbound/senders.py: LogSender (data/runtime/outbox.jsonl) and SmtpSender (TODO).
- API: GET /api/drafts?status=, POST /api/drafts/generate, GET/PATCH /api/drafts/{id}, POST /api/drafts/{id}/approve
  (= approve and send), /reject, /send (retry). Also GET /api/clients, /api/risk, /api/events, POST /api/events/scan,
  POST /api/connectors/email/sync, POST /api/system/reset, GET /api/system/health. Full list: http://localhost:8000/docs.
- Frontend: typed client `api` + `unwrap` in frontend/src/api/client.ts (openapi-fetch); UI strings in frontend/src/i18n.ts.

## Data conventions
snake_case everywhere incl. TS. Timestamps UTC "…Z" in data; DISPLAY in Europe/Sofia (or the destination's zone for slot
times). Money{amount_minor:int, currency}, display only via formatters (bg: "1 250,00 EUR"). Languages bg/en/ru/tr/ro.
Enums lowercase snake_case from the generated types. UTF-8; Cyrillic as-is; no transliteration. "Now" in the backend
only via app.core.clock.now() (fixed demo clock 2026-10-15T07:30:00Z).

## Prioritized tasks
1. Live LLM: copy .env.example to .env, set LLM_MODE=live + a Gemini key; make payment_reminder (bg, firm) and delay_notice
   (en, formal/apologetic) read naturally. Have a native speaker review the Bulgarian. Keep canned mocks in sync for every kind.
2. Queue UX for the demo: clear cards, "Why" rationale, fallback tag, edit → save → approve, reject with reason,
   history with sent status, empty/error/loading states, a confirm step before sending.
3. Delay notice polish: slot/ETA in the destination time zone (Munich = Europe/Berlin); use B's data["reason"] when present.
4. One reminder per client covering all overdue invoices (de-dupe in proactive.py); mark events handled on send.
5. SMTP sandbox sender (Mailtrap/MailHog; OUTBOUND_MODE=smtp), UTF-8 subjects/bodies; never real client addresses.
6. Client detail view: profile factors with evidence, invoices, emails timeline, "Draft…" buttons; BG/EN UI toggle complete.
7. STRETCH: quote_reply draft for feed emails (tr/en) incl. "prepayment recommended" if B flags it; invoice/CMR documents
   (DraftChannel.document) as simple HTML/PDF; truck map (Leaflet + OSM) from /api/trucks/{id}/positions; SSE instead of polling.

## Definition of done
`npm run check` green (backend tests + `npm run typecheck`); the approval-gate test still passes; the demo flow in
docs/DEMO_SCRIPT.md works by clicking in under 3.5 minutes on both mock and live LLM; README "Drafting, outbound & UI (C)"
section. Small PRs from c/<topic>, merged at least every 2–3 hours, with a screenshot for UI PRs.

## Integration points
B: get_profile() → tone + factors to display; events → proactive drafts. A: emails linked to clients (timeline) and
new mail via connector sync. Lead: system prompt/LLM wrapper changes. D: Bulgarian wording feedback. The UI is what judges
see, so rehearse with the team at the T+5 and T+10 checkpoints.

Start by reading CONVENTIONS.md, docs/DEMO_SCRIPT.md, backend/app/schemas/drafts.py, backend/app/drafting/, backend/app/outbound/
and frontend/src/. Then propose a short plan for task 1 and implement it.
```
