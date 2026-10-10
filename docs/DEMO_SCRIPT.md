# Demo script (3:30 min)

**Setup:** `.env` has `LLM_MODE=live` (Gemini), `LLM_FALLBACK_TO_MOCK=true` and `APP_ENV=demo`. Press **Reset demo** right before going on stage. Have a second laptop running the same build in mock mode as a hot spare, plus a screen recording of a full run as the last resort.

| Time | Screen | Say |
|---|---|---|
| 0:00–0:30 | Title slide | "Small Sofia forwarders run on email, Excel, a GPS portal and an ERP that don't talk to each other. A dispatcher finds out a truck is late when the client calls angry. The accountant chases the same late payer every month by hand. Ivan is an AI colleague that sits on top of the tools they already have." |
| 0:30–1:00 | Dashboard: clients with risk | Click **Балкан Стил** to open its factors: "Every score is explained. +34: paid 8 of 8 invoices late, 34 days on average. +25: EUR 4,010 overdue, oldest 45 days. No black box." Click **Rhein**: "Pays early, but fined us twice for missing delivery slots, so it's strict." |
| 1:00–1:20 | Press **Scan for events** | "Ivan watches GPS, invoices and email. It just noticed two things." Events appear: *SPD-2026-0901 projected 2h20m late* and *Invoice 0000000801 is 45 days overdue*. |
| 1:20–2:10 | Queue → Rhein draft | "Truck 3 has been stuck 3h40m at the Batrovci border. Tomorrow's 08:00 slot at Rhein is binding. Ivan drafted an English heads-up **before the client notices**, in a formal tone because this client fines delays. Look at **Why**: it explains its reasoning." Edit one word and press **Save** to show it's editable. Press **Approve & send**. "Nothing leaves without this click." |
| 2:10–2:50 | Queue → Балкан Стил draft | "Same engine, different client: a Bulgarian reminder in a firm tone, because this is the third reminder. It uses only facts from our data and never mentions the risk score to the client." **Approve & send** → History shows *sent*. |
| 2:50–3:10 | **Sync inbox** | "New mail just came in. Балкан Стил wants a new quote while still owing us EUR 4,000. That's exactly when you want a risk profile next to the email." (Stretch: show the prepayment suggestion.) |
| 3:10–3:30 | Architecture slide | "Built to self-host: every connector is swappable from mock to real, and the language model is a config switch to a local model. Today we use a hosted model on **synthetic data**; in production client data stays on the company's server. Bulgarian first; English, Romanian and Turkish already flow through." |

## What must really work (no faking)
- Detectors → events → drafts → approve → sent, live in the UI.
- Explainable risk factors computed from the seed data.
- **One real LLM call per draft** in live mode (the mock fallback is only a safety net; the "fallback" tag shows if it kicked in).
- Approval gate: `send` returns 409 without approval (show `/docs` if a judge asks).

## What is faked / mocked (say so if asked)
- All data is synthetic; connectors replay seed feeds (IMAP/GPS/ERP connectors are optional stretch work).
- "Send" writes to `data/runtime/outbox.jsonl` or to a sandbox SMTP inbox (Mailtrap/MailHog), never to real addresses.
- The hero truck's ETA is seeded; projecting ETA from GPS is B's stretch goal.
- The clock is fixed at Thu 15 Oct 2026, 10:30.

## Failure drills (rehearse at least twice)
| Failure | Recovery |
|---|---|
| Gemini 429 or slow | Fallback fires automatically; or switch to `LLM_MODE=mock` and restart (10 s) |
| Draft has wrong facts or language | Edit in the textarea before approving ("that's why there's a human in the loop") |
| Backend crash | `npm run dev` again; the DB persists. Then **Reset demo** |
| Laptop/Wi-Fi dies | Spare laptop (mock mode) → screen recording |
