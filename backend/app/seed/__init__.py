"""Seeded mock-data generator. Run: `npm run seed` (or `uv run python -m app.seed.generate` in backend/).

story.py       demo storyline constants (lead)      - IDs the demo script and tests rely on
places.py      cities / waypoints (shared)
gen_business.py clients, trucks, shipments, invoices, payments, incidents (owner B)
gen_tracking.py GPS pings (owner A)
gen_comms.py   emails, documents, connector feeds (owner A)
generate.py    orchestrates, validates, writes data/seed/ (lead)
"""
