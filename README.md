# Ivan — AI assistant for freight forwarders

Commands:

```
npm run dev (uv run uvicorn app.main:app --reload --port 8000,
node node_modules/vite/bin/vite.js
),
docker compose up -d central-db

cd C:\school\IvanTheForwarder\backend
uv run uvicorn central.main:app --port 8100

```

A self-hostable assistant for small/medium Bulgarian freight forwarders (спедитори). It sits **on top of**
the tools a forwarder already uses (email, documents, GPS, ERP), profiles clients with **explainable**
risk scores, and drafts emails/documents into a **"ready to send" queue — nothing leaves without a human click**.

> Hackathon MVP. Everything runs on **mock data** by default. Live analysis uses Claude through Anthropic's API.

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

### Live Traccar GPS

The default GPS data is seeded mock data. To read live positions from Traccar, configure a test Traccar
server in `.env`:

```env
CONNECTOR_GPS=traccar
TRACCAR_URL=https://traccar.example.com
TRACCAR_TOKEN=your-api-token
TRACCAR_DEVICE_MAP=12:trk_0003,13:trk_0004
```

`TRACCAR_DEVICE_MAP` maps Traccar device IDs to existing Ivan truck IDs. You can use
`TRACCAR_USER` and `TRACCAR_PASSWORD` instead of a token. Then restart the backend and use
`POST /api/connectors/gps/sync` or the API connector controls. Traccar speed is converted from knots
to km/h; positions are stored as `GpsPing` records and are used by the map and delay detection.

### MP3 call extraction

The dashboard's **Process call recording** action accepts MP3, WAV, M4A, and OGG files. Ivan stores the
recording locally, transcribes it, extracts logistics fields, and shows the transcript and missing fields
for human review. Confirming the reviewed fields adds a `phone_call` load to the existing Loads section.
No load is created automatically.

The default mode is safe mock mode:

```env
STT_MODE=mock
STT_API_KEY=
STT_MODEL=whisper-1
```

Audio is stored under `data/runtime/calls/`; obtain the required consent before recording calls and define
an appropriate retention/deletion policy for production use.

## Commands (repo root)

| Command                  | What                                                                 |
| ------------------------ | -------------------------------------------------------------------- |
| `npm run dev`            | start both servers (hot reload)                                      |
| `npm test`               | backend tests incl. the schema/contract gate                         |
| `npm run typecheck`      | frontend TS check                                                    |
| `npm run gen:types`      | schemas → `shared/openapi.json` → `frontend/src/api/schema.ts`       |
| `npm run seed`           | regenerate `data/seed/` (deterministic)                              |
| `npm run check`          | everything CI runs                                                   |
| `POST /api/system/reset` | wipe DB, reload seed (demo rehearsal) — also the "Reset demo" button |

## Layout & ownership

```
backend/app/
  schemas/      ★ single source of truth for data shapes ............ lead (schema owner)
  core/         config, clock, ids, formatting ........................ lead
  repository/   SQLite JSON-doc store + SeedStore ..................... lead
  llm/          Claude wrapper, system prompt, mock mode ................ lead
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

The folder watcher reads PDF files placed in `docs/incoming/`. In mock mode, searchable invoices are parsed locally
for invoice number, customer, total, currency, and due date; a uniquely matched past-due invoice PDF adds an
explainable risk factor. Documents with ambiguous customer matches are stored but do not affect a client's score.
Scanned PDFs and other document types need `LLM_MODE=live`, `LLM_PROVIDER=anthropic`, and a valid API key for
full extraction. The dashboard refreshes risk profiles automatically.

### Risk & events (B)

Client risk is a transparent score: start at 30, add the impact of each listed factor, then clamp to 0–100.
Every factor includes its measured values and links to the supporting invoices, shipments, incidents, or emails.
The profile also reports confidence and a suggested message tone; it never sends a message. Email response
time is measured only for replies linked by an explicit thread ID. Try the demo with `npm run dev`, then
select a client or use **Scan for events** to see the risk profile and event evidence.

Margin risk is based on average shipment margin (price minus cost, divided by price); margins below 12% are
flagged with the thinnest observed lane. Damage/claim incidents, delay complaints, incompatible cargo
restrictions, and email replies averaging at least 48 hours add their own evidence-backed factors. Missing
source data is left unknown rather than guessed. Linked email insights (including exact invoice numbers and
complaint/delay intent) can support invoice and delay factors. Document extractions are matched by stored
links or unique exact invoice/shipment references, and Traccar GPS positions are matched to a shipment by
its ID or a unique truck/time window. These files and GPS points corroborate existing risk evidence; they do
not create standalone risk signals or replace invoice/payment records.

### Drafting, outbound & UI (C)

The approval queue supports mock/live LLM drafts, editable subject/body, rationale and fallback indicators,
rejection reasons, confirmation before sending, and sent/failed history. Payment reminders are de-duplicated
per client and include all overdue invoices. Delay notices display destination-local times (including
Europe/Berlin for German deliveries), and successfully sent event drafts mark their source event handled.
The default log sender writes to `data/runtime/outbox.jsonl`; `OUTBOUND_MODE=smtp` enables UTF-8 STARTTLS
delivery to a sandbox such as Mailtrap or MailHog. The dashboard includes Bulgarian/English UI strings,
loading/error states, explainable risk factors, events, and the client draft actions.
Client detail pages show risk evidence, invoices, email history, and incidents. A Leaflet/OpenStreetMap
truck-position view is available from the dashboard. Invoice and CMR draft kinds produce simple UTF-8
HTML document bodies; PDF export, feed-aware quote replies, prepayment recommendations, and SSE updates
remain planned follow-ups.
