"""Central index API + the public search page for outsiders. Run: `uvicorn central.main:app --port 8100` (from backend/). Owner: lead.

  PUT    /api/v1/companies/{uid}   a company publishes its profile      (Bearer CENTRAL_INGEST_TOKEN)
  DELETE /api/v1/companies/{uid}   a company withdraws: the row is deleted (Bearer CENTRAL_INGEST_TOKEN)
  GET    /api/v1/search            outsiders search/match companies      (public, read-only)
  GET    /api/v1/companies/{uid}   one profile                           (public, read-only)
  GET    /                         the search page

KNOWN LIMIT: one shared ingest token means any holder can overwrite any company. Issue a per-company key at sign-up before
real use, and add rate limits/API keys to the read endpoints before exposing them to the internet.
"""

import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from psycopg.types.json import Jsonb
from pydantic import StringConstraints

from app.schemas import CargoType, Language, TrailerType
from app.schemas.common import ContractModel, CountryCode
from app.schemas.network import PublicCompanyProfile
from central import search
from central.config import get_settings
from central.db import apply_schema, get_conn

log = logging.getLogger("central")
STATIC = Path(__file__).parent / "static"
SUPPORTED_SCHEMA_VERSION = 1
MAX_LIMIT = 50

Uid = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{8,64}$")]
Lane = Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}-[A-Z]{2}$")]


class Match(ContractModel):
    profile: PublicCompanyProfile
    rank: float  # free-text relevance (0 when no text was searched)


class SearchResponse(ContractModel):
    total: int
    items: list[Match]


@asynccontextmanager
async def lifespan(_: FastAPI):
    apply_schema()
    log.warning("central index ready")
    yield


app = FastAPI(title="Freight network: central index", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    # profiles contain free text written by companies: the page must never run it, so no inline script and no third parties
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def require_ingest_token(authorization: str | None = Header(default=None)) -> None:
    expected = get_settings().central_ingest_token
    if not expected:
        raise HTTPException(503, "publishing is disabled: CENTRAL_INGEST_TOKEN is not set")
    given = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not secrets.compare_digest(given.encode(), expected.encode()):
        raise HTTPException(401, "invalid token")


UPSERT = """
INSERT INTO companies (company_uid, name, name_latin, home_region, countries, trailer_types, cargo_types, languages, adr,
                       max_load_kg, fleet_trucks, fleet_max_capacity_kg, lanes, public_notes, contact_email, contact_phone,
                       profile, schema_version, published_at, received_at)
VALUES (%(uid)s, %(name)s, %(name_latin)s, %(region)s, %(countries)s, %(trailers)s, %(cargo)s, %(languages)s, %(adr)s,
        %(max_load)s, %(trucks)s, %(capacity)s, %(lanes)s, %(notes)s, %(email)s, %(phone)s,
        %(profile)s, %(version)s, %(published_at)s, now())
ON CONFLICT (company_uid) DO UPDATE SET
    name = EXCLUDED.name, name_latin = EXCLUDED.name_latin, home_region = EXCLUDED.home_region, countries = EXCLUDED.countries,
    trailer_types = EXCLUDED.trailer_types, cargo_types = EXCLUDED.cargo_types, languages = EXCLUDED.languages, adr = EXCLUDED.adr,
    max_load_kg = EXCLUDED.max_load_kg, fleet_trucks = EXCLUDED.fleet_trucks, fleet_max_capacity_kg = EXCLUDED.fleet_max_capacity_kg,
    lanes = EXCLUDED.lanes, public_notes = EXCLUDED.public_notes, contact_email = EXCLUDED.contact_email,
    contact_phone = EXCLUDED.contact_phone, profile = EXCLUDED.profile, schema_version = EXCLUDED.schema_version,
    published_at = EXCLUDED.published_at, received_at = now()
WHERE companies.published_at <= EXCLUDED.published_at
"""


@app.put("/api/v1/companies/{company_uid}", status_code=204, dependencies=[Depends(require_ingest_token)])
def put_company(company_uid: Uid, body: PublicCompanyProfile, conn=Depends(get_conn)) -> None:
    if body.company_uid != company_uid:
        raise HTTPException(422, "company_uid in the body must match the path")
    if body.schema_version != SUPPORTED_SCHEMA_VERSION:
        raise HTTPException(422, f"unsupported schema_version {body.schema_version}")
    doc = body.model_dump(mode="json")
    conn.execute(UPSERT, {
        "uid": company_uid, "name": body.name, "name_latin": body.name_latin, "region": body.home_region,
        "countries": doc["countries_served"], "trailers": doc["trailer_types"], "cargo": doc["cargo_types"], "languages": doc["languages"],
        "adr": body.adr, "max_load": body.max_load_kg, "trucks": body.fleet.trucks, "capacity": body.fleet.max_capacity_kg,
        "lanes": Jsonb(doc["lanes"]), "notes": body.public_notes, "email": body.contact_email, "phone": body.contact_phone,
        "profile": Jsonb(doc), "version": body.schema_version, "published_at": body.updated_at,
    })


@app.delete("/api/v1/companies/{company_uid}", status_code=204, dependencies=[Depends(require_ingest_token)])
def delete_company(company_uid: Uid, conn=Depends(get_conn)) -> None:
    """Withdrawal: the company's row is deleted, nothing is kept. Idempotent."""
    conn.execute("DELETE FROM companies WHERE company_uid = %s", (company_uid,))


@app.get("/api/v1/companies/{company_uid}")
def get_company(company_uid: Uid, conn=Depends(get_conn)) -> PublicCompanyProfile:
    row = conn.execute("SELECT profile FROM companies WHERE company_uid = %s", (company_uid,)).fetchone()
    if row is None:
        raise HTTPException(404, "no such company")
    return PublicCompanyProfile.model_validate(row["profile"])


@app.get("/api/v1/search")
def search_companies(
    country: Annotated[list[CountryCode], Query(description="serves ALL of these countries")] = [],
    lane: Annotated[list[Lane], Query(description="runs ALL of these lanes, e.g. BG-DE")] = [],
    trailer: Annotated[list[TrailerType], Query(description="has ANY of these trailer types")] = [],
    cargo: Annotated[list[CargoType], Query(description="handles ALL of these cargo types")] = [],
    language: Annotated[list[Language], Query(description="speaks ANY of these languages")] = [],
    min_load_kg: Annotated[int | None, Query(ge=0)] = None,
    adr: bool = False,
    region: Annotated[str, Query(max_length=100)] = "",
    q: Annotated[str, Query(max_length=200, description="free text over name, region and notes")] = "",
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    conn=Depends(get_conn),
) -> SearchResponse:
    filters = search.Filters(countries=country, lanes=lane, trailers=[t.value for t in trailer], cargo=[c.value for c in cargo],
                             languages=[x.value for x in language], min_load_kg=min_load_kg, adr=adr, region=region.strip(), q=q.strip())
    total, rows = search.run(conn, filters, limit, offset)
    return SearchResponse(total=total, items=[Match(profile=PublicCompanyProfile.model_validate(r["profile"]), rank=float(r["rank"])) for r in rows])


@app.get("/", include_in_schema=False)
def page() -> FileResponse:
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
