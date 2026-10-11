"""Capacity profile shared with the central network (opt-in). Aggregates only: no client, price, plate, driver or invoice is ever
included. Owner: lead."""

from pydantic import Field

from app.schemas.common import ContractModel, CountryCode, EmailAddress, PhoneE164, UtcDatetime
from app.schemas.enums import CargoType, Language, TrailerType


class ProfileSettingsInput(ContractModel):
    """What the company decides. Blank lists / no max load = taken from our own fleet and history."""

    consent: bool = False  # nothing is sent unless true
    share_contact: bool = False
    home_region: str = ""
    countries_served: list[CountryCode] = []
    max_load_kg: int | None = Field(default=None, ge=0)
    trailer_types: list[TrailerType] = []
    cargo_types: list[CargoType] = []
    adr: bool = False  # dangerous goods
    languages: list[Language] = []
    public_notes: str = ""
    contact_email: EmailAddress | None = None
    contact_phone: PhoneE164 | None = None


class ProfileSettings(ProfileSettingsInput):
    id: str = "profile"  # single record
    company_uid: str  # random, stable id of this company in the central index
    last_published_at: UtcDatetime | None = None
    last_publish_status: str = ""


class LaneStat(ContractModel):
    from_country: CountryCode
    to_country: CountryCode
    shipments: int  # last 12 months; lanes with very few shipments are left out so one client cannot be recognised


class FleetSummary(ContractModel):
    trucks: int  # own fleet only
    trailer_types: list[TrailerType]
    max_capacity_kg: int


class PublicCompanyProfile(ContractModel):
    """Exactly what would be sent to the central index."""

    schema_version: int = 1
    company_uid: str
    name: str
    name_latin: str
    home_region: str
    countries_served: list[CountryCode]
    lanes: list[LaneStat]
    fleet: FleetSummary
    max_load_kg: int
    trailer_types: list[TrailerType]
    cargo_types: list[CargoType]
    adr: bool
    languages: list[Language]
    public_notes: str
    contact_email: EmailAddress | None = None  # only when share_contact
    contact_phone: PhoneE164 | None = None
    updated_at: UtcDatetime


class PublicProfileState(ContractModel):
    settings: ProfileSettings
    preview: PublicCompanyProfile
