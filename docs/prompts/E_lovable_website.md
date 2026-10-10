# Prompt for Person E — Marketing website in Lovable

How to use: open https://lovable.dev → New project → paste the whole block below as the first message. Then iterate with
short follow-ups (e.g. "make the hero shorter", "add the FAQ section"). Publish, and send the link to the team chat by
**T+5h** (v1) and **T+16h** (final, with D's verified numbers). This site is the public story, not the product UI.

```text
Build a modern, single-page marketing website (with an optional /bg version) for "Ivan", an AI assistant for freight
forwarding companies in Bulgaria. React + Tailwind. Responsive, fast, accessible (WCAG AA contrast), no login, no backend.

## Brand
- Name: Ivan (Bulgarian: Иван). Tagline: "Your forwarding team's AI colleague." / BG: "AI колегата на Вашия спедиторски екип."
- Personality: calm, competent, trustworthy, practical. A reliable dispatcher, not a flashy startup.
- Visual style: clean, lots of white space; deep navy (#0F2A44) as the primary colour, signal amber (#F5A524) as the accent
  (like a truck's warning light), soft grey backgrounds (#F4F6F8). Font: Inter (it supports Cyrillic), large readable headings.
- Imagery: abstract road/route lines and map-like line art, a truck silhouette, UI mockups of an approval queue. No stock
  photos of people shaking hands, no robots.
- Add a language toggle EN / BG in the header that switches all copy (use the BG texts provided below; keep a simple
  translation dictionary).

## Pages / sections (single page with anchor navigation)
1. Header: logo wordmark "Ivan", nav (Problem, How it works, Privacy, Who it's for, Contact), EN/BG toggle, button "See the demo".
2. Hero
   EN H1: "Your forwarding team's AI colleague."
   EN sub: "Ivan reads your email, documents, GPS and ERP, warns you before problems hit, and drafts the messages you
   need — every one waits for your approval."
   BG H1: "AI колегата на Вашия спедиторски екип."
   BG sub: "Иван чете пощата, документите, GPS и ERP системата Ви, предупреждава преди проблемите да ударят и подготвя
   нужните съобщения — всяко чака Вашето одобрение."
   Buttons: "See the demo" (scroll to Demo), "Talk to us" (scroll to Contact).
   Visual: a mockup card "Ready to send" showing: "Truck 3 is ~2h late (border queue at Batrovci). Rhein Logistik is strict
   on slots → heads-up email drafted. [Approve & send] [Edit]".
3. Problem (3 cards)
   - "Five tools, zero overview." Email, Excel, the GPS portal, the ERP, the phone. Nothing talks to anything.
   - "You find out last." The client calls about the late truck before you know it's late.
   - "Chasing the same payers." The same clients pay late every month, and someone writes the same reminder by hand.
   BG: "Пет програми, никаква обща картина." / "Научавате последни." / "Гоните едни и същи длъжници."
4. Solution / How it works (4 steps with icons)
   1) Connect: works on top of the tools you already use: email, documents (CMR, invoices, rate sheets), GPS/telematics,
      your ERP (even via screenshots when there's no integration).
   2) Understand: builds an explainable profile of every client: payment habits, fines, delay sensitivity, cargo they
      accept or refuse, margin per route. Every score shows its reasons.
   3) Act early: notices events (a truck running late, an overdue invoice) and drafts the right message in the right tone
      and language.
   4) You decide: everything lands in a "Ready to send" queue. Nothing is sent without your click.
5. Feature highlights (grid): Explainable client risk · Proactive delay heads-ups · Payment reminders in the right tone ·
   Bulgarian & English (Romanian, Turkish, Russian planned) · Works alongside your TMS/ERP, not instead of it · Human approval for everything.
6. Privacy & self-hosting
   EN: "Built to run on your own server. Ivan is designed to be self-hosted, so client and pricing data can stay inside your
   company. The AI model is a configuration choice: a hosted model, or a local one running on your own hardware."
   Small print: "Our hackathon prototype uses a hosted AI model with synthetic demo data. The production setup runs the
   model locally."
   BG: "Създаден да работи на Вашия сървър. Иван е проектиран за собствен хостинг, така че данните за клиенти и цени
   могат да останат във фирмата. AI моделът е въпрос на настройка — облачен или локален, на Вашия хардуер."
   BG small print: "Хакатон прототипът използва облачен AI модел със синтетични демо данни. Продукционната версия работи с локален модел."
7. Who it's for: small and medium forwarders (спедиторски фирми) in Sofia and Bulgaria with 3–50 people, working
   international road freight to the EU, the Balkans and Turkey; dispatchers, accountants, owners. Three mini-personas:
   Dispatcher ("knows about delays first"), Accountant ("reminders that write themselves, in the right tone"),
   Owner ("sees which clients are worth it").
8. Demo: an embedded video placeholder (16:9) titled "3-minute demo", with a caption "Prototype built at Crossroads AI Hackathon 2026".
9. FAQ (accordion): "Does it replace our TMS?" No, it works on top of it. · "Will it send emails by itself?" Never; a person
   approves every message. · "Where is our data?" Designed to stay on your server (see Privacy). · "Which languages?" Bulgarian
   and English today; Romanian, Turkish and Russian planned. · "What does it cost?" Pilot pricing on request.
10. Contact: a simple form (name, company, email, message) that only shows a "Thanks!" message (no backend), plus a
    "Join the pilot" line. Footer: "© 2026 Ivan — Crossroads AI Hackathon prototype", plus a link to the team.

## Tone of copy
Plain, concrete, forwarder vocabulary (slot, CMR, ETA, border, invoice, payment terms). Short sentences. Bulgarian copy must
use formal "Вие/Ви" and natural business Bulgarian, not machine-translated phrasing.

## DO NOT claim (very important)
- Do not say "fully local", "your data never leaves your office" or "100% private" as a current fact. Say "designed to be
  self-hosted" / "can stay inside your company".
- Do not show customer logos, testimonials, user counts, "trusted by", awards, or certifications (ISO, SOC2, GDPR-certified).
- Do not present planned features as available: real ERP/GPS/IMAP integrations, Romanian/Turkish/Russian, e-CMR,
  mobile app, automatic sending.
- Do not claim specific % savings or ROI numbers unless a sourced figure is provided later.
- Do not say it is a TMS, or that it replaces dispatchers or accountants.
- No fake pricing tables.
```
