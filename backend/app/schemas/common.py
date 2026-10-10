"""Shared primitives. See CONVENTIONS.md for the rules these types enforce. Owner: lead."""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, PlainSerializer, StringConstraints

from app.schemas.enums import EntityType

SCHEMA_VERSION = "1.0.0"  # bump minor for additive changes, major for breaking ones


class ContractModel(BaseModel):
    """Base for every shared model. extra="forbid": unknown fields are an error, not silently kept."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)


# ---------- timestamps: timezone-aware in, UTC out, serialized as 2026-10-15T07:30:00Z ----------
def _to_utc(v: datetime) -> datetime:
    return v.astimezone(UTC).replace(microsecond=0)


UtcDatetime = Annotated[
    AwareDatetime,
    AfterValidator(_to_utc),
    PlainSerializer(lambda v: v.strftime("%Y-%m-%dT%H:%M:%SZ"), return_type=str, when_used="json"),
]


# ---------- IDs: <prefix>_<4-32 lowercase alphanumerics> ----------
def _id(prefix: str):
    return Annotated[str, StringConstraints(pattern=rf"^{prefix}_[a-z0-9]{{4,32}}$")]


ClientId = _id("cli")
TruckId = _id("trk")
GpsPingId = _id("gps")
ShipmentId = _id("shp")
EmailId = _id("eml")
DocumentId = _id("doc")
InvoiceId = _id("inv")
PaymentId = _id("pay")
IncidentId = _id("inc")
CallLogId = _id("cal")
EventId = _id("evt")
DraftId = _id("drf")
EnvelopeId = _id("env")

# ---------- codes ----------
CountryCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}$")]  # ISO 3166-1 alpha-2
CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]  # ISO 4217
EmailAddress = Annotated[str, StringConstraints(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", to_lower=True)]
PhoneE164 = Annotated[str, StringConstraints(pattern=r"^\+[1-9][0-9]{6,14}$")]
Ratio = Annotated[float, Field(ge=0.0, le=1.0)]  # 0..1, never percent


class Money(ContractModel):
    """Integer minor units (cents/stotinki) + ISO 4217 code. Never floats."""

    amount_minor: int
    currency: CurrencyCode

    @classmethod
    def of(cls, amount_minor: int, currency: str = "EUR") -> "Money":
        return cls(amount_minor=amount_minor, currency=currency)


class Location(ContractModel):
    city: str  # original script, e.g. "София", "München"
    country: CountryCode
    postal_code: str | None = None
    address: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)


class EvidenceRef(ContractModel):
    """Points at the stored object that justifies a claim (risk factor, event, draft)."""

    entity_type: EntityType
    entity_id: str
    note: str | None = None
