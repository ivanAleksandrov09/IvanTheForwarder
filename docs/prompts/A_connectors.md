# Prompt for Person A — Data gathering & connectors (paste into Claude Code, opened in the repo root)

```text
You are my pair programmer at a 24-hour hackathon. I am Person A on a 5-person team.

## Project
"Ivan" is a self-hostable AI assistant for small Bulgarian freight forwarders (спедитори, Sofia). It sits ON TOP of the
tools a forwarder already uses (email, documents, GPS/telematics, ERP), profiles clients with explainable risk scores,
and drafts emails/documents into a "ready to send" queue; nothing is sent without a human click. Everything runs on
MOCK data; real connectors must be swappable for mock ones with zero changes outside the connectors folder.
Monorepo: FastAPI + Pydantic v2 + SQLite backend (backend/app), React/Vite/TS frontend. Start with `npm run dev`.

## My responsibility: data gathering
Priority: (1) company email, (2) documents (CMR, invoices, rate sheets, transport orders), (3) GPS/trucks, (4) ERP.
Only after those four work: call logs, ERP screenshots via vision/OCR, external sources (web search, speditor.net:
its API is UNVERIFIED, so build a mock feed first and flag the risk).

## Files I own (work ONLY here)
backend/app/connectors/**  · backend/app/api/data.py · backend/app/seed/gen_comms.py · backend/app/seed/gen_tracking.py
· the FEED_MODELS dict in backend/app/repository/seed_store.py · backend/tests/test_connectors*.py · my README section.
Do NOT edit backend/app/schemas/** (lead only), core/, repository/repo.py, llm/client.py, or other owners' folders.
If I need a new field or enum value, STOP and write me a short "schema change request" (model, field, type, why) to
post in team chat. Never invent fields, never stash data in ad-hoc dicts, never read files directly.

## Contracts (already in the repo, read them first)
- backend/app/schemas/: Email, Document, GpsPing, Truck, Client, Shipment, Invoice, Payment, Incident, CallLog;
  ConnectorEnvelope{envelope_id, schema_version, source, connector, fetched_at, external_id, payload_type, payload}.
- backend/app/connectors/base.py: BaseConnector with ClassVars name/source/mode/description, fetch(since)->list[ConnectorEnvelope],
  health(), info(), and wrap(payload, external_id) which builds the envelope. Connectors NEVER write to the DB.
- backend/app/connectors/email_mock.py is the REFERENCE connector: copy its pattern.
- backend/app/connectors/registry.py picks ONE active connector per SourceType from env (CONNECTOR_EMAIL=mock|imap, ...).
- backend/app/connectors/ingest.py: sync(connector, repo) is the only path from connector output into the repository.
- Mock connectors read data/seed/feeds/<feed>.json via SeedStore.load_feed(); every feed must be registered in FEED_MODELS.
- Repository: repo.emails.upsert(obj), repo.clients.list(country="BG"), repo.shipments.list(where=lambda s: ...).
- API: GET /api/connectors, POST /api/connectors/{source}/sync -> SyncResult.

## Data conventions (enforced by validators and tests)
IDs `<prefix>_<4-32 lowercase a-z0-9>` (cli trk gps shp eml doc inv pay inc cal evt drf env); new runtime ids via app.core.ids.new_id("eml").
Timestamps: aware datetimes, stored as UTC "…Z"; "now" ONLY via app.core.clock.now() (the demo runs on a fixed clock 2026-10-15T07:30:00Z).
Money: Money{amount_minor:int, currency:"EUR"}, never floats. Units in field names (_kg, _km, _minutes). Countries ISO alpha-2, languages bg/en/ru/tr/ro.
Enums: lowercase snake_case from schemas/enums.py only. Unknown = null; lists default [].
Text: UTF-8, Cyrillic stored as-is, no transliteration. Bulgarian email may arrive as windows-1251/koi8-r: decode to UTF-8.
Document.extracted_fields keys: cmr: cmr_number, sender_name, consignee_name, place_of_taking_over, place_of_delivery,
gross_weight_kg, vehicle_plate · invoice: invoice_number, issue_date, due_date, total_minor, currency, vat_number ·
transport_order: delivery_slot, pallets, gross_weight_kg · rate_sheet: lane, currency, valid_until.
Seed data is generated deterministically by `npm run seed` (never hand-edit data/seed/*.json); IDs in app/seed/story.py must not change.

## Prioritized tasks
1. Ingest: link inbound emails to clients (sender address/domain vs Client.contacts), dedupe by external_id, use
   connector.last_sync_at for incremental sync. Tests.
2. gen_comms.py: grow to ~30 base emails (bg/en/ro/tr/ru; threads via thread_id; signatures; one forwarded chain) and
   3–4 feed emails. Keep the existing hero emails (eml_0001–0007) and feed eml_0101/0102 unchanged.
3. Documents mock connector (feeds/documents_inbox.json → Document) incl. extracted_fields; register in registry + FEED_MODELS.
4. GPS mock connector replaying feeds/gps_live.json for the hero truck trk_0003 (stays stuck at Batrovci; each sync = next pings);
   gen_tracking.py: 7-day history for all trucks.
5. ERP mock connector (feeds/erp_invoices.json + erp_payments.json → Invoice/Payment), e.g. a new payment arriving.
6. Emit DomainEvent(email_received/document_received) on new items ONLY after agreeing the shape with B (events owner).
7. STRETCH: IMAP connector (email_imap.py, CONNECTOR_EMAIL=imap, test with a throwaway mailbox); ERP screenshot → vision
   via the LLM wrapper (ask the lead to add an image-capable method; never call openai directly); call logs; speditor.net
   (check whether an API exists; otherwise mock feed external_web.json with clearly labelled sample data; never scrape behind a login).

## Definition of done (per task)
- `npm run check` passes (contract tests validate every mock connector's envelopes and every seed/feed file).
- Works with CONNECTOR_*=mock and no network. Real connectors fail soft (SyncResult.errors, never crash the app).
- New tests in backend/tests/test_connectors*.py. README "Connectors (A)" section: what works, env vars, how to try it.
- Small PR from branch a/<topic>, merged at least every 2–3 hours.

## Integration points
- B reads emails/GPS/incidents/payments from the repository for risk and delay detection: tell B when GPS/ETA data changes shape or meaning.
- C shows emails per client and relies on Email.client_id linking.
- Lead: schema change requests, and LLM vision support for screenshots.
Deliverables go to the team via PRs to main; demo-relevant changes get announced in team chat.

Start by reading CONVENTIONS.md, docs/ARCHITECTURE.md, backend/app/schemas/, and backend/app/connectors/. Then propose
a short plan for task 1 and implement it.
```
