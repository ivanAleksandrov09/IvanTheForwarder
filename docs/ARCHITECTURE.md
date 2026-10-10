# Architecture & decisions

## Assumptions (change them here if wrong)
1. **24-hour hackathon**, judging at the end; the timeline in [PLAN.md](PLAN.md) is written in hour offsets (T+0…T+24). Shorter event: compress phases proportionally and use the cut list.
2. **Tech lead = schema owner = Ivan** (the person who set up this repo), and also one of A/B/C. GitHub handles in `.github/CODEOWNERS` are placeholders.
3. Everyone on A/B/C can install Node 20+, Python 3.11+ and `uv`. Windows, macOS and Linux all work; line endings are normalised by `.gitattributes`.
4. No authentication in the MVP: single operator, `reviewed_by` is free text.
5. Demo "now" is fixed at **Thu 15 Oct 2026, 10:30 Sofia time** (`DEMO_NOW`) so the story is identical on every machine.
6. Product working name: **"Ivan"** (Иван), an assistant that sounds like a colleague. Rename freely.
7. Bulgaria has used the euro since 1 Jan 2026, so all seed money is EUR.

## Stack (recommendation + reason)
| Layer | Choice | Why |
|---|---|---|
| Backend | **Python 3.11+, FastAPI, Pydantic v2** | Pydantic is both the validator and the schema source. FastAPI emits OpenAPI for free. Python has the best LLM/OCR/email libraries. |
| Storage | **SQLite, one table of JSON docs** (`collection, id, data`) behind a typed repository | No migrations during a hackathon. Every read and write passes through the Pydantic model. Self-hostable as a single file. |
| Frontend | **React 19 + Vite + TypeScript**, `openapi-fetch` typed client | Fastest dev loop; generated types make API drift a compile error. |
| Types | Pydantic → OpenAPI (`shared/openapi.json`) → `openapi-typescript` → `frontend/src/api/schema.ts` | One direction, zero hand-written duplicates. CI checks both artefacts are fresh. |
| LLM | `openai` Python SDK against any **OpenAI-compatible** endpoint | Gemini, OpenAI and Ollama all speak this protocol, so switching provider is just a config change. |
| Runner | root `package.json` + `concurrently`; `uv` for Python | `npm install && npm run dev` is the whole setup on every OS. |
| Deploy (pitch) | single machine / office server; Docker Compose is a stretch goal | Shows the "self-hostable" story. |

## Runtime picture
```
 Browser (React, :5173) ──/api/*──▶ Vite dev proxy ──▶ FastAPI (:8000)
                                                         │
     ┌─────────────── api/ (one router per owner) ───────┤
     │                                                   │
 connectors/ (A) ─▶ ConnectorEnvelope ─▶ ingest ─▶ repository ◀─ risk/ (B), events/ (B)
     ▲ mock: data/seed/feeds/*.json                      │              │ DomainEvent
     ▲ real: IMAP, folder+OCR, GPS API, ERP              │              ▼
                                                         │        drafting/ (C) ─▶ llm/ wrapper ─▶ Gemini | OpenAI | Ollama | mock
                                                         │              │ DraftMessage (pending_review)
                                                         ▼              ▼
                                                   SQLite file     outbound/ (C): human approve ─▶ sender (log | smtp sandbox)
```
- **Frontend ↔ backend:** REST/JSON under `/api`, same origin through the Vite proxy (so no CORS issues in dev). The UI polls every 5 s; SSE is a stretch goal.
- **Module ↔ module (inside the backend):** plain Python calls to each module's public function (`risk.scoring.get_profile`, `events.detectors.run_detectors`, `drafting.service.generate_draft`, `outbound.queue.send_draft`). Modules only exchange schema objects.
- **Hero loop:** `POST /api/events/scan` → detectors (B) → `DomainEvent` → `drafting.proactive` (C) → risk profile (B) picks the tone → LLM returns validated `DraftContent` → `DraftMessage{pending_review}` → UI → `POST /drafts/{id}/approve` → `send_draft()` refuses anything that isn't human-approved → sender → outbound `Email` recorded.

## LLM wrapper (`backend/app/llm/`)
- `client.py` provides `complete_text(task, prompt, mock_context)` and `complete_json(task, prompt, schema, mock_context)`, and nothing else. No module imports `openai` directly.
- **Config only:** `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_MODE=mock|live`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`, `LLM_TEMPERATURE`, `LLM_JSON_MODE`, `LLM_FALLBACK_TO_MOCK`, `LLM_LOG_PROMPTS`.
- **System message** (`system_prompt.py`) sets the role ("Ivan", drafts only), the no-invention rule (placeholders such as `[ДАТА]` instead of made-up facts), the internal-data rule (never mention risk scores to clients), language rules (Bulgarian formal Вие, number and date formats, no transliteration), tone definitions and the JSON-only output rule.
- **Robustness:**
  - Retries with exponential backoff and jitter on 429/5xx/timeouts/connection errors, and honours `Retry-After`. No retry on 4xx.
  - Per-request timeout.
  - `complete_json` embeds the JSON Schema, strips code fences, validates with Pydantic, and gets one repair round-trip on invalid output.
  - Falls back to canned responses (`mock_responses.py`) when the API is down. The draft is flagged `llm.used_fallback=true` and the UI shows a "fallback" tag.
- **Log:** `data/runtime/logs/llm.jsonl` records every prompt, response, latency and error. It is gitignored because it contains client data.
- **Verified in the skeleton:** mock mode end to end; live mode against Gemini with a bad key (400 → falls back to mock without retrying); live mode against an unreachable host (retries → falls back).

### Stage 1 → Stage 2 (local model)
```env
LLM_MODE=live
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen2.5:7b-instruct     # good multilingual (bg/ru/tr/ro) quality at 7B
LLM_API_KEY=ollama
LLM_JSON_MODE=true                # Ollama supports response_format json_object
```
No code changes. Set up with `ollama pull qwen2.5:7b-instruct`. Expect slower and somewhat weaker Bulgarian output, so bump the timeout to 120 s. Alternatives to test: `gemma3:12b`, `llama3.1:8b`.

### Honesty: stage 1 is only acceptable because the data is fake
The stage-1 hosted API receives the prompt text. That is fine **only** because every client, invoice and email in the demo is generated mock data. Pitch wording:
> "Ivan is **designed** to run fully on-premise: the language model is a config switch. For this demo we use a hosted model on **synthetic data**. In production the same code points at a local model, so client and pricing data never leave the company's server."

Don't say "runs fully local" or "your data never leaves your office" unless stage 2 is actually running in the demo.

## REST API (generated docs: http://localhost:8000/docs)
| Method & path | Owner | Returns | Notes |
|---|---|---|---|
| GET `/api/system/health` | lead | `HealthResponse` | app clock, LLM status |
| GET `/api/system/llm` | lead | `LlmStatus` | |
| POST `/api/system/llm/ping` | lead | `LlmPingResponse` | hello-world LLM call |
| POST `/api/system/reset` | lead | `ResetResponse` | wipe + reload seed (dev/demo only) |
| GET `/api/clients`, `/api/clients/{id}` | A | `Client[]`, `Client` | |
| GET `/api/trucks`, `/api/trucks/{id}/positions` | A | `Truck[]`, `GpsPing[]` | |
| GET `/api/shipments?status=&client_id=`, `/api/shipments/{id}` | A | `Shipment[]`, `Shipment` | |
| GET `/api/emails?client_id=` · `/api/documents` · `/api/invoices` · `/api/payments` · `/api/incidents` | A | lists | |
| GET `/api/connectors` | A | `ConnectorInfo[]` | |
| POST `/api/connectors/{source}/sync` | A | `SyncResult` | source = `email`, `documents`, `gps`, `erp`, … |
| GET `/api/risk` | B | `RiskProfile[]` | all clients |
| GET `/api/clients/{id}/risk` | B | `RiskProfile` | explainable factors + evidence |
| GET `/api/events` | B | `DomainEvent[]` | |
| POST `/api/events/scan?auto_draft=true` | B (+C glue) | `DomainEvent[]` | runs detectors; high-severity events get drafts |
| GET `/api/drafts?status=` | C | `DraftMessage[]` | the queue |
| POST `/api/drafts/generate` | C | `DraftMessage` | body `GenerateDraftRequest` |
| GET / PATCH `/api/drafts/{id}` | C | `DraftMessage` | PATCH body `UpdateDraftRequest` (only while pending) |
| POST `/api/drafts/{id}/approve` | C | `DraftMessage` | **the human confirmation**: approves, then sends |
| POST `/api/drafts/{id}/reject` | C | `DraftMessage` | |
| POST `/api/drafts/{id}/send` | C | `DraftMessage` | retries a failed send; 409 unless human-approved |

Errors: 404 `NotFoundError`, 409 `ConflictError` (invalid state transition), 502 `LLMError`, 422 validation.

## Shared contracts — where they live
| Contract | File |
|---|---|
| Primitives (`Money`, `Location`, `UtcDatetime`, ID types, `EvidenceRef`, `SCHEMA_VERSION`) | `backend/app/schemas/common.py` |
| Enums (single canonical list) | `backend/app/schemas/enums.py` |
| `Client`, `Contact`, `Truck`, `GpsPing`, `Shipment`, `Email`, `Document`, `Invoice`, `Payment`, `Incident`, `CallLog` | `backend/app/schemas/entities.py` |
| `RiskProfile`, `RiskFactor`, `ClientMetrics` | `backend/app/schemas/risk.py` |
| `DomainEvent` | `backend/app/schemas/events.py` |
| `DraftMessage` (= NotificationItem), `DraftContent` (LLM output), request bodies, `LlmMeta`, `SendResult` | `backend/app/schemas/drafts.py` |
| `ConnectorEnvelope` (= ConnectorEvent), `ConnectorInfo`, `SyncResult` | `backend/app/schemas/connectors.py` |
| Connector interface `BaseConnector` | `backend/app/connectors/base.py` |
| Collection registry (`COLLECTIONS`, `SEED_COLLECTIONS`) | `backend/app/schemas/__init__.py` |
| Type generation | `backend/scripts/export_openapi.py` + `frontend` script `gen:types` (`npm run gen:types`) |
| Validation gate | `backend/tests/test_contracts.py` |
