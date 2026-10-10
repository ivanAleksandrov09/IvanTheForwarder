# Ivan — AI assistant for freight forwarders

A self-hostable assistant for small/medium Bulgarian freight forwarders (спедитори). It sits **on top of**
the tools a forwarder already uses (email, documents, GPS, ERP), profiles clients with **explainable**
risk scores, and drafts emails/documents into a **"ready to send" queue — nothing leaves without a human click**.

> Hackathon MVP. Everything runs on **mock data** by default. LLM stage 1 uses a hosted API (Gemini/OpenAI)
> through one OpenAI-compatible wrapper; stage 2 swaps to local Ollama by changing `.env` only.

## Quick start (new teammate, ~5 min)
Prerequisites: **Node 20+**, **Python 3.11+**, **[uv](https://docs.astral.sh/uv/getting-started/installation/)**, git.

```bash
git clone <repo-url> && cd IvanTheForwarder
npm install          # installs root tools, backend (uv sync) and frontend
npm run dev          # backend :8000 + frontend :5173
```
Open http://localhost:5173 → press **Scan for events** → two drafts appear → **Approve & send**.
API docs: http://localhost:8000/docs

Optional: `cp .env.example .env` and set `LLM_MODE=live` + `LLM_API_KEY=...` (free Gemini key from
https://aistudio.google.com/apikey). Without a key everything works in mock mode.

## Commands (repo root)
| Command | What |
|---|---|
| `npm run dev` | start both servers (hot reload) |
| `npm test` | backend tests incl. the schema/contract gate |
| `npm run typecheck` | frontend TS check |
| `npm run gen:types` | schemas → `shared/openapi.json` → `frontend/src/api/schema.ts` |
| `npm run seed` | regenerate `data/seed/` (deterministic) |
| `npm run check` | everything CI runs |
| `POST /api/system/reset` | wipe DB, reload seed (demo rehearsal) — also the "Reset demo" button |

## Layout & ownership
```
backend/app/
  schemas/      ★ single source of truth for data shapes ............ lead (schema owner)
  core/         config, clock, ids, formatting ........................ lead
  repository/   SQLite JSON-doc store + SeedStore ..................... lead
  llm/          OpenAI-compatible wrapper, system prompt, mock mode ... lead
  connectors/   email/documents/gps/erp connectors + ingest .......... A
  risk/         explainable client scoring ............................ B
  events/       detectors (overdue, delay, ...) ....................... B
  drafting/     LLM drafting + event→draft glue ....................... C
  outbound/     approval state machine + senders ...................... C
  seed/         mock-data generator (gen_business=B, gen_comms/gen_tracking=A, rest=lead)
  api/          system.py=lead · data.py=A · risk.py=B · drafts.py=C
backend/tests/  test_contracts.py (lead) · add test_<module>.py per owner
frontend/       React + Vite + TS UI .................................. C
shared/         generated openapi.json (never edit by hand)
data/seed/      generated seed + feeds/ (committed) · data/runtime/ (DB, logs; gitignored)
docs/           architecture, demo script, plan, mock data, teammate prompts
```
Read **[CONVENTIONS.md](CONVENTIONS.md)** before your first commit. Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Module notes
<!-- Each owner adds a short section here: what works, how to try it, env vars, known gaps. -->
### Connectors (A)
TODO(owner A)
### Risk & events (B)
Client risk is a transparent score: start at 30, add the impact of each listed factor, then clamp to 0–100.
Every factor includes its measured values and links to the supporting invoices, shipments, incidents, or emails.
The profile also reports confidence and a suggested message tone; it never sends a message. Email response
time is measured only for replies linked by an explicit thread ID. Try the demo with `npm run dev`, then
select a client or use **Scan for events** to see the risk profile and event evidence.

Margin risk is based on average shipment margin (price minus cost, divided by price); margins below 12% are
flagged with the thinnest observed lane. Damage/claim incidents, delay complaints, incompatible cargo
restrictions, and email replies averaging at least 48 hours add their own evidence-backed factors. Missing
source data is left unknown rather than guessed.
### Drafting, outbound & UI (C)
The approval queue supports mock/live LLM drafts, editable subject/body, rationale and fallback indicators,
rejection reasons, confirmation before sending, and sent/failed history. Payment reminders are de-duplicated
per client and include all overdue invoices. Delay notices display destination-local times (including
Europe/Berlin for German deliveries), and successfully sent event drafts mark their source event handled.
The default log sender writes to `data/runtime/outbox.jsonl`; `OUTBOUND_MODE=smtp` enables UTF-8 STARTTLS
delivery to a sandbox such as Mailtrap or MailHog. The dashboard includes Bulgarian/English UI strings,
loading/error states, explainable risk factors, events, and the client draft actions.
