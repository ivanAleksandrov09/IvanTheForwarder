"""Build the public capacity profile from our own data + what the company chose. Aggregates only. Owner: lead."""

import secrets
from collections import Counter
from datetime import datetime, timedelta

from app.repository import Repository
from app.schemas import (
    CompanyInput,
    FleetSummary,
    LaneStat,
    ProfileSettings,
    PublicCompanyProfile,
    ShipmentStatus,
)

MIN_LANE_SHIPMENTS = 3  # smaller lanes could point at a single client, so they are not published
TOP_LANES = 10


def settings_record(repo: Repository) -> ProfileSettings:
    saved = repo.network_profile.get("profile")
    return saved or repo.network_profile.upsert(ProfileSettings(company_uid=secrets.token_hex(8)))


def build_profile(repo: Repository, company: CompanyInput, s: ProfileSettings, now: datetime) -> PublicCompanyProfile:
    own = [t for t in repo.trucks.list() if t.is_own_fleet]
    since = now - timedelta(days=365)
    recent = repo.shipments.list(
        where=lambda x: x.status != ShipmentStatus.cancelled and x.status != ShipmentStatus.quoted and x.pickup_planned_at >= since
    )
    lanes = Counter((x.origin.country, x.destination.country) for x in recent)
    fleet_trailers = sorted({t.trailer_type for t in own}, key=lambda v: v.value)
    max_capacity = max((t.capacity_kg for t in own), default=0)
    return PublicCompanyProfile(
        company_uid=s.company_uid,
        name=company.name,
        name_latin=company.name_latin,
        home_region=s.home_region,
        countries_served=s.countries_served or sorted({c for x in recent for c in (x.origin.country, x.destination.country)}),
        lanes=[LaneStat(from_country=a, to_country=b, shipments=n) for (a, b), n in lanes.most_common() if n >= MIN_LANE_SHIPMENTS][:TOP_LANES],
        fleet=FleetSummary(trucks=len(own), trailer_types=fleet_trailers, max_capacity_kg=max_capacity),
        max_load_kg=s.max_load_kg if s.max_load_kg is not None else max_capacity,
        trailer_types=s.trailer_types or fleet_trailers,
        cargo_types=s.cargo_types or sorted({x.cargo_type for x in recent}, key=lambda v: v.value),
        adr=s.adr,
        languages=s.languages or sorted({c.preferred_language for c in repo.clients.list()}, key=lambda v: v.value),
        public_notes=s.public_notes,
        contact_email=s.contact_email if s.share_contact else None,
        contact_phone=s.contact_phone if s.share_contact else None,
        updated_at=now,
    )
