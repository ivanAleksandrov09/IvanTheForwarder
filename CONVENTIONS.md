# Conventions (one page — read before your first commit)

**One source of truth:** every data shape lives in `backend/app/schemas/` (Pydantic v2). Frontend types are
**generated** from it (`npm run gen:types` → `shared/openapi.json` → `frontend/src/api/schema.ts`). Nobody
hand-writes a duplicate type, dict shape or TS interface.

## Data rules (enforced by validators + `backend/tests/test_contracts.py`)
| Topic | Rule | Example |
|---|---|---|
| IDs | `<prefix>_<4–32 lowercase a-z0-9>`; seed uses readable numbers, runtime uses `new_id(prefix)`; events use `stable_id()` | `cli_0001`, `drf_3f9a1c0b7e2d4a51` |
| Prefixes | `cli trk gps shp eml doc inv pay inc cal evt drf env` | |
| Timestamps | timezone-aware in, stored/serialized **UTC with `Z`**, second precision. Convert to `Europe/Sofia` only for display | `2026-10-15T07:30:00Z` |
| "Now" | only `app.core.clock.now()` — never `datetime.now()` (demo runs on a fixed clock) | |
| Money | `Money{amount_minor:int, currency:ISO 4217}` — **never floats**. Bulgaria uses EUR since 1 Jan 2026; BGN only for historical docs | `{"amount_minor":348000,"currency":"EUR"}` |
| Units | in the field name: `_kg` (int), `_km` (float), `_minutes`/`_seconds` (int), `_kmh`, `_deg`, `_pct` (display only) | `weight_kg`, `delay_minutes` |
| Ratios | float 0..1 (`Ratio`), never percent | `on_time_payment_rate: 0.83` |
| Countries | ISO 3166-1 alpha-2, uppercase | `BG`, `DE` |
| Languages | ISO 639-1 enum: `bg en ru tr ro` | |
| Enums | lowercase snake_case, defined once in `schemas/enums.py` | `pending_review` |
| Null vs optional | every field is always present in JSON. Unknown = `null`. Lists default `[]`, never `null`. (Only exception: PATCH bodies, where `null` = unchanged) | |
| Naming | snake_case everywhere — backend, JSON **and** generated TS (no camelCase conversion) | `client_id` |
| Text | UTF-8, Cyrillic stored as-is, names in original script, **no transliteration**. `name_latin` only if the entity itself uses one | `"Балкан Стил ООД"` |
| Unknown fields | rejected (`extra="forbid"`). Need a field? Request a schema change — don't stash it in a dict | |
| `Document.extracted_fields` keys | `cmr`: cmr_number, sender_name, consignee_name, place_of_taking_over, place_of_delivery, gross_weight_kg, vehicle_plate · `invoice`: invoice_number, issue_date, due_date, total_minor, currency, vat_number · `transport_order`: delivery_slot, pallets, gross_weight_kg · `rate_sheet`: lane, currency, valid_until | |

## Data flow rules
- Only `app/repository/` touches the DB; only `SeedStore` reads `data/seed/`. No ad-hoc file reads.
- Connectors return `list[ConnectorEnvelope]` only; `connectors/ingest.py` is the only path into the DB.
- Seed data comes from ONE generator (`npm run seed`, deterministic). Never hand-edit `data/seed/*.json`.
- Outgoing messages: `DraftMessage` → human approves → `outbound.send_draft()`. Nothing else sends.
- Internal data (risk scores, notes, margins) never goes into client-facing text.

## How to change a schema
1. Post in the team chat: *what* field/enum, *why*, and *who is affected*.
2. The **schema owner (lead)** makes the change in `backend/app/schemas/` on a branch `schema/<what>` — small PR, nothing else in it.
3. In the same PR: `npm run seed` (if seed is affected), `npm run gen:types`, `npm test`, and commit `shared/openapi.json` + `frontend/src/api/schema.ts` + `data/seed/`.
4. Additive change → bump `SCHEMA_VERSION` minor; rename/remove → major and tell every owner before merging.
5. After the merge, everyone runs `git pull --rebase origin main` and `npm run gen:types`.

CI (`.github/workflows/ci.yml`) fails if seed, connector output or the committed OpenAPI/TS types drift from the schemas.
