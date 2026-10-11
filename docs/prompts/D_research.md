# Prompt for Person D — Research & pitch material (paste into any AI chat with web search: ChatGPT, Gemini, Perplexity, Claude)

How to deliver: create one Google Doc per section in the shared folder **"Ivan – Research"** (link from the lead), and paste
the AI's answers there. Put the source link next to every number. Then tell the team chat "Section N ready". You never need GitHub.
Deadlines: sections 1–2 by **T+5h**, 3–4 by **T+10h**, 5–6 by **T+16h**.

```text
You are a market and regulatory research assistant helping a hackathon team prepare a pitch. Work section by section;
after each section, stop and wait for me to say "next".

## The product
"Ivan" is an AI assistant for small and medium freight forwarding companies ("спедитори") in Bulgaria, starting in Sofia.
- It connects to the tools a forwarder already uses (company email, documents such as CMRs, invoices and rate sheets,
  GPS/telematics, the company's ERP, phone call logs, screenshots of ERP software when there's no API) and acts as an
  intelligent layer on top of them. It is NOT a replacement for a transport management system (TMS).
- It profiles clients with EXPLAINABLE risk scores (late payments, fines, delay sensitivity, cargo preferences, per-route margin).
- It prepares outgoing emails, messages, invoices and CMRs in a "ready to send" queue. A human approves every message.
- It is designed to be self-hosted, so client and pricing data can stay inside the company. Bulgarian + English first,
  with Russian, Turkish and Romanian planned.
- It is proactive. Example: "truck 3 is 2h late + this client fines delays → a drafted heads-up email is waiting for approval".

## Rules for your answers
- Cite a source (URL + publisher + year) for EVERY number or factual claim.
- Mark anything you cannot verify as [UNVERIFIED]. Mark your own estimates as [ESTIMATE] and show the calculation.
- Prefer primary sources: НСИ/NSI (Bulgarian National Statistical Institute), Eurostat, the EU Commission, IRU, UNECE,
  company websites, official registries. Bulgarian-language sources are welcome; summarise them in English.
- Be concise: tables and bullet points. No marketing language.

## Section 1 — Competitor table
Columns: name | HQ | what it does | AI features | deployment (cloud SaaS / on-prem / hybrid) | tied to its own TMS? |
languages incl. Bulgarian? | target customer size | pricing if public | source.
Must include: Logistaas (Averroes AI), CargoWise (WiseTech), Transporeon/Trimble, Alpega, Timocom (and its tools),
Shipamax, Raft.ai, Magaya, at least 2 "agentic TMS" / AI-email-drafting tools for forwarders (e.g. rate-sheet parsing
and email automation startups), and any Bulgarian or CEE TMS/ERP used by local forwarders (e.g. local accounting/ERP
vendors that forwarders use in Bulgaria). End with 5 bullets: where Ivan is genuinely different (self-hostable, works across
existing tools, proactive, explainable, Bulgarian), and where competitors are clearly stronger.

## Section 2 — Bulgarian market & pain points
- Number of freight forwarding / road transport companies in Bulgaria and in Sofia, with size distribution (micro/small/medium).
  NACE codes 49.41 (freight transport by road) and 52.29 (other transportation support activities, which includes forwarding).
- Market size / revenue of the sector, road freight volumes, share of international transport, main corridors
  (e.g. to DE, RO, TR, GR, Western Balkans).
- Bulgaria's eurozone accession (1 Jan 2026): impact on invoicing and payments.
- Top pain points of small forwarders: late payments and payment terms in transport, fines/penalties for missed slots,
  border waiting times (Kapitan Andreevo, Kalotina, Ruse–Giurgiu, Kulata, the Schengen effect since 2024–2025), driver shortage,
  email/phone overload, manual documents. Find quotes from Bulgarian industry associations (e.g. АБА / Bulgarian Association of
  Freight Forwarders, НСБПП / road hauliers' associations) and forums.
- Late payment statistics in transport (EU Late Payment Directive, Intrum European Payment Report or similar, Bulgarian data).

## Section 3 — Regulations relevant to the product
- CMR Convention basics (liability, delay liability, documents) and the status of e-CMR in Bulgaria (ratification of the
  e-CMR additional protocol; is it usable today?).
- EU eFTI Regulation (EU) 2020/1056: timeline, and what it means for digital transport documents.
- GDPR as applied to an AI assistant that processes client emails and call logs; lawful basis; DPIA need; why self-hosting
  helps; obligations of the hosted-LLM data processor; EU AI Act classification of this use case (likely limited/minimal risk?).
- Bulgarian e-invoicing / invoice requirements (10-digit invoice numbering, VAT on international transport services),
  and any SAF-T / e-invoicing timeline in Bulgaria.
- Mobility Package rules that create events worth monitoring (driver rest times, return of trucks).

## Section 4 — Pitch statistics (top 10)
The 10 strongest, verifiable numbers for a 3-minute pitch (e.g. hours per week dispatchers spend on email, % of invoices
paid late in transport, average days sales outstanding (DSO) in Bulgarian transport, cost of a missed delivery slot, number of target companies).
For each: the number, a one-sentence pitch phrasing, the source, and a confidence rating (high/medium/low).

## Section 5 — Judges' objection-handling sheet
For each likely objection, give a 2–3 sentence honest answer:
"Isn't this just ChatGPT with extra steps?" · "Why not use Logistaas/CargoWise?" · "Is the data really private if you use
Gemini or another provider?" (honest answer: the demo uses a hosted model on synthetic data; the design swaps to a local model by
config) · "Will small forwarders pay? How much?" · "What if the AI sends something wrong?" (human approval on every
message) · "How do you integrate with ERPs that have no API?" (screenshots + vision, CSV exports) · "Bulgarian LLM quality?"
· "Liability for wrong risk scores / GDPR profiling of clients (companies vs natural persons)?" · "Go-to-market in Sofia?"
· "What's built vs. planned?"

## Section 6 — Pricing & business model sketch
Comparable SaaS prices for small logistics companies in CEE. Propose 2–3 pricing options for a self-hosted product
(setup fee + monthly per user/per truck) with reasoning, marked [ESTIMATE].
```
