# Prompt for Person B — Risk assessment & client profiling (paste into Claude Code, opened in the repo root)

```text
You are my pair programmer at a 24-hour hackathon. I am Person B on a 5-person team.

## Project
"Ivan" is a self-hostable AI assistant for small Bulgarian freight forwarders (спедитори, Sofia). It gathers data
(email, documents, GPS, ERP), profiles clients with EXPLAINABLE risk scores, notices events (truck late, invoice
overdue), and drafts tone-appropriate messages into an approval queue; nothing is sent without a human click.
Everything runs on deterministic MOCK data. Monorepo: FastAPI + Pydantic v2 + SQLite backend (backend/app),
React/Vite/TS frontend. Start with `npm run dev`.

## My responsibility: risk & profiling + event detection
Late payment behaviour, slowness, fines/penalties, cargo types they want or refuse, per-route margin, damage claims.
Scores MUST be explainable: score = BASE + sum(RiskFactor.impact); every factor has a sentence WITH numbers and
EvidenceRefs to the invoices/incidents/emails behind it. Never a black-box number. Also: event detectors (the proactive layer),
and realism of the business mock data.

## Files I own (work ONLY here)
backend/app/risk/** · backend/app/events/** · backend/app/api/risk.py · backend/app/seed/gen_business.py ·
backend/tests/test_risk*.py, test_events*.py · my README section.
Do NOT edit backend/app/schemas/** (lead only) or other owners' folders. Need a new field/enum (e.g. a new
RiskFactorCode or EventType)? STOP and write a short schema change request (model, field, type, why) for team chat.
Never invent fields; DomainEvent.data is display-only and logic must not depend on its keys.

## Contracts (already in the repo, read them first)
- schemas/risk.py: RiskProfile{client_id, computed_at, score 0..100 (higher = riskier), level low|medium|high|unknown,
  confidence, factors[RiskFactor{code, label, impact -100..100, explanation, evidence[]}], metrics: ClientMetrics,
  observed_cargo_types, recommended_tone formal|friendly|firm|apologetic, summary, scoring_version}.
- RiskFactorCode: late_payment_history, currently_overdue, good_payment_history, delay_sensitivity, fines_history,
  damage_claims, low_margin, slow_communication, cargo_restrictions, insufficient_history.
- schemas/events.py: DomainEvent{id = stable_id("evt", type, entity_id) for idempotency, type, severity, occurred_at,
  detected_at, client/shipment/truck/invoice ids, title, description, data, evidence, handled, draft_ids}.
- risk/scoring.py: compute_profile() and get_profile(client_id, repo, now). C's drafting calls get_profile() and uses
  recommended_tone, so keep that signature stable.
- events/detectors.py: pure detectors (repo, now) -> list[DomainEvent], DETECTORS list, run_detectors() preserves handled/draft_ids.
- C's drafting/proactive.py turns HIGH/CRITICAL invoice_overdue and shipment_delayed events into drafts automatically.
- API: GET /api/risk, GET /api/clients/{id}/risk, GET /api/events, POST /api/events/scan.
- Repository: repo.invoices.list(client_id=...), repo.payments.list(...), repo.incidents.list(...), repo.gps_pings.list(truck_id=...).
- Places/border crossings for delay reasons: backend/app/seed/places.py KNOWN_PLACES.

## Data conventions
IDs `<prefix>_<lowercase a-z0-9>`. Timestamps UTC "…Z"; "now" ONLY via app.core.clock.now() (fixed demo clock
2026-10-15T07:30:00Z; never datetime.now()). Money{amount_minor:int, currency} with no floats (ratios 0..1 floats ok,
_pct for display). Units in field names. Enums lowercase snake_case from schemas/enums.py. Unknown = null, lists default [].
UTF-8, Cyrillic as-is. "Overdue" is NOT an invoice status; derive it from due_at vs now. Seed: deterministic generator
(`npm run seed`), never hand-edit JSON; hero IDs in app/seed/story.py must not change.

## Demo story you must keep true (tests check it)
- cli_0001 Балкан Стил: chronic late payer, inv_0801 is 45 days overdue → level high, tone firm, factors
  late_payment_history + currently_overdue. Event invoice_overdue (high) for inv_0801.
- cli_0002 Rhein Logistik: pays early, 2 fines for late slots → tone formal; shp_0901 (truck trk_0003, stuck 3h40m at
  Batrovci) projected 2h20m late → event shipment_delayed (high).
- Control cases: shp_0902 on time, shp_0903 25 min late (below threshold): no events.

## Prioritized tasks
1. Remaining factors: low_margin (avg_margin_pct, per route), damage_claims, cargo_restrictions (requested vs
   refused_cargo_types, e.g. Trakia refuses ADR), delay_sensitivity (penalty/complaint emails, fines), slow_communication
   (email response times). Unit tests for each with hand-built repos.
2. Tune weights/levels so the 8 clients spread sensibly (high/medium/low/unknown); add confidence logic.
3. Delay detector v2: project ETA from GPS pings (remaining km / recent avg speed + mandatory rest), fill
   data["reason"] e.g. "stationary 3h40m at Batrovci (RS/HR border)" using KNOWN_PLACES, so C's draft can cite the reason.
4. More detectors: payment_received, truck_idle, risk_level_changed; email_received urgency (agree the shape with A).
5. gen_business.py realism: partial payments, Trakia seasonality, Vardar erratic, delay incidents, thin Pernik→Bucharest margins.
6. STRETCH: "prepayment recommended" signal when a high-risk client asks for a new quote (feed email eml_0101); an
   LLM-written 2-sentence internal summary via app.llm (complete_text/complete_json only; add a canned mock
   to llm/mock_responses.py under task "risk.summary").

## Definition of done
`npm run check` green; story tests in backend/tests/test_hello_world.py still pass; every factor has explanation + evidence;
README "Risk & events (B)" section explains the scoring formula in plain words (C and the pitch reuse it).
Small PRs from b/<topic>, merged at least every 2–3 hours.

## Integration points
C consumes get_profile() (recommended_tone, factors for the UI) and events (proactive drafting). A produces the emails/GPS
you read. Tell the lead about any schema need early. D can sanity-check what Bulgarian forwarders actually consider
"risky" clients; ask via the team chat.

Start by reading CONVENTIONS.md, docs/MOCK_DATA.md, backend/app/schemas/risk.py, backend/app/risk/scoring.py and
backend/app/events/detectors.py. Then propose a short plan for task 1 and implement it.
```
