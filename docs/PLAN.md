# Plan: timeline, git workflow, risks

## Timeline (assumes 24 h; scale proportionally for other lengths)
| Time | Phase | A (connectors) | B (risk/events) | C (drafts/UI) | D (research) | E (website) |
|---|---|---|---|---|---|---|
| T+0–1 | **Kickoff** | clone, `npm install`, `npm run dev`, read CONVENTIONS | same | same | gets prompt + shared Drive folder | gets Lovable prompt |
| T+1–5 | **Build 1 (MVP core)** | email mock → 30 emails, client linking in ingest, documents mock connector | all risk factors + tests, delay detector reads GPS | Gemini live drafts in bg/en, queue UX, SMTP sandbox | competitor table, pain points | site v1 live |
| **T+5** | ✅ **Checkpoint 1**: all merged, `npm run check` green, hero loop on live Gemini | | | | first research doc | |
| T+5–10 | **Build 2** | GPS connector + live feed for the hero truck, ERP mock (invoices/payments CSV) | ETA projection + delay reason (border), payment_received event, per-route margin | client detail page, events → draft links, language toggle, quote_reply draft | regulations, market size, stats | site v2 + copy from D |
| **T+10** | ✅ **Checkpoint 2**: full demo path rehearsed once, end to end | | | | pitch numbers | |
| T+10–16 | **Build 3 (stretch, pick ≤2)** | IMAP connector **or** ERP-screenshot vision **or** speditor.net | "prepayment recommended" on quote requests; LLM-written risk summary | truck map; CMR/invoice document drafts | objection sheet | final |
| T+12 | (sleep in shifts: at most 2 people off at the same time; never A, B and C all at once) | | | | | |
| **T+16** | 🧊 **FEATURE FREEZE**: only bug fixes, seed polish, demo hardening | | | | | |
| T+16–20 | **Harden** | seed realism | seed realism, thresholds | UI polish, fallback tag, error states | slides with lead | link on slides |
| T+20–22 | **Rehearse** ×3 (live, live with Wi-Fi off → fallback, spare laptop) + record a backup video | | | | | |
| T+22–24 | Pitch prep, buffer, submit | | | | | |

Integration checkpoints are hard stops: everyone merges to `main`, pulls, and runs `npm run check` plus the demo click-through together (15 min).

### MVP (must ship) vs stretch
**MVP:** seed story · email + documents + GPS mock connectors · explainable risk (payments, overdue, fines, low margin, insufficient history) · overdue and delay detectors · live LLM drafts in bg and en with tone from the profile · approval queue with edit/approve/reject · send to log or sandbox SMTP · reset button · demo script rehearsed.

**Stretch (in this order):** ETA from GPS → quote request with prepayment advice → client detail page → ERP mock connector → truck map → IMAP real mailbox → ERP screenshot via vision → call logs → speditor.net / web search → Ollama stage 2 live → ru/tr/ro UI.

### If behind, cut in this order
1. Anything from the stretch list (start from the bottom).
2. Real (non-mock) connectors of any kind; mock connectors are enough for the demo.
3. Truck map and client detail page; the dashboard alone carries the demo.
4. SMTP; the log sender is fine ("sandboxed send").
5. Extra draft kinds; keep only `payment_reminder` and `delay_notice`.
6. **Never cut:** explainable factors, the approval gate, live LLM call plus fallback, the rehearsals.

## Git workflow (A, B, C)
- `main` is always demo-able. Protect it: PR required, CI green, 1 approval (any other dev; schema PRs need the lead).
- Branches: `a/<topic>`, `b/<topic>`, `c/<topic>`, `schema/<topic>` (lead only). Short-lived: **merge at least every 2–3 hours**.
- **Folder ownership = no conflicts:**
  - A: `connectors/`, `api/data.py`, `seed/gen_comms.py`, `seed/gen_tracking.py`, `repository/seed_store.py` (FEED_MODELS only)
  - B: `risk/`, `events/`, `api/risk.py`, `seed/gen_business.py`
  - C: `drafting/`, `outbound/`, `api/drafts.py`, `llm/mock_responses.py` (draft entries), `frontend/`
  - lead: `schemas/`, `core/`, `repository/`, `llm/client.py`, `llm/system_prompt.py`, `main.py`, `seed/story.py`, `seed/generate.py`, `tests/test_contracts.py`
  - Touching someone else's folder → ask in chat first, keep the change tiny, tag them on the PR.
- Generated files (`shared/openapi.json`, `frontend/src/api/schema.ts`, `data/seed/**`): never edit by hand. On a merge conflict, take either side, then re-run `npm run seed && npm run gen:types`.
- PR rules: < ~400 lines, one topic, `npm run check` passes locally, no new fields outside `schemas/`, README module section updated, screenshot for UI changes.
- Commit style: `A: email mock links sender domain to client`.

### Exact first commands
```bash
# lead, once:
git add -A && git commit -m "Scaffold: schemas, repo layer, LLM wrapper, mock connector, seed, UI hello world"
git remote add origin git@github.com:<org>/IvanTheForwarder.git && git push -u origin main
# then on GitHub: Settings → Branches → protect main (require PR + status check "ci")

# A / B / C, each:
git clone git@github.com:<org>/IvanTheForwarder.git && cd IvanTheForwarder
npm install && npm run dev            # open http://localhost:5173, press "Scan for events"
git switch -c a/email-connector       # b/risk-factors, c/live-drafts
# ...work...
npm run check
git add -A && git commit -m "A: ..." && git push -u origin HEAD
gh pr create --fill                   # or open the PR in the browser
# stay fresh, at least every 2 hours:
git fetch origin && git rebase origin/main
```

## Top risks & mitigations
| # | Risk | Likelihood / impact | Mitigation |
|---|---|---|---|
| 1 | **Demo failure** (crash, Wi-Fi, LLM down) | M / fatal | Fixed clock and seed; **Reset demo** button; automatic mock fallback; spare laptop in mock mode; recorded video; 3 rehearsals |
| 2 | **API rate limits** during rehearsals | H / M | Backoff with Retry-After; mock mode for development (default); live only for rehearsals; ~2 LLM calls per demo |
| 3 | **Bulgarian output quality** (calques, wrong formality, gender agreement) | M / M | Strict system prompt (Вие, formats, placeholders); D or a native speaker reviews 5 sample drafts at T+5; tune prompts; editable drafts are the safety net; neutral "Здравейте, {име}" salutation |
| 4 | **Schema drift / merge breakage** | M / H | One schema owner; `extra="forbid"`; contract tests and type-freshness check in CI; small PRs; generated files regenerated, never merged by hand |
| 5 | **Merge conflicts** | M / M | Folder ownership; one router file per owner; merge every 2–3 h; checkpoints |
| 6 | **Integration unknowns** (IMAP auth, GPS vendor APIs, ERP has no API) | H / L | All demo-critical paths use mock connectors; real ones are stretch goals behind the same interface; ERP screenshot via vision is the "no API" story |
| 7 | **speditor.net access** (API unverified, ToS, scraping blocked) | H / L | Treat as stretch; mock feed `feeds/external_web.json` with clearly labelled sample data; D checks ToS and whether an API exists; never scrape behind a login |
| 8 | **Time / scope creep** | H / H | Feature freeze at T+16; cut list above; lead says no to new features after T+10 |
| 9 | **Over-claiming in the pitch** (privacy, "fully local") | M / H with judges | Honest wording in ARCHITECTURE.md; E's "do not claim" list; show the config switch |
| 10 | **Data protection** (real personal data slipping into a hosted LLM) | L / H | Only synthetic data in stage 1; `.env` and `data/runtime/` are gitignored; logs stay local |
