"""Search over the central index: hard filters in SQL, free text ranked with Postgres full-text search. Owner: lead."""

from dataclasses import dataclass, field

from psycopg.types.json import Jsonb


@dataclass
class Filters:
    countries: list[str] = field(default_factory=list)  # must serve ALL of these
    lanes: list[str] = field(default_factory=list)  # "BG-DE": must run ALL of these lanes
    trailers: list[str] = field(default_factory=list)  # has ANY of these
    cargo: list[str] = field(default_factory=list)  # handles ALL of these
    languages: list[str] = field(default_factory=list)  # speaks ANY of these
    min_load_kg: int | None = None
    adr: bool = False
    region: str = ""
    q: str = ""


def _like(value: str) -> str:
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def where_clause(f: Filters) -> tuple[str, dict]:
    """Every value is a bound parameter: nothing user-supplied is ever put into the SQL text."""
    where, params = ["true"], {}
    if f.countries:
        where.append("countries @> %(countries)s::text[]")
        params["countries"] = f.countries
    for i, lane in enumerate(f.lanes):
        origin, destination = lane.split("-")
        where.append(f"lanes @> %(lane{i})s")
        params[f"lane{i}"] = Jsonb([{"from_country": origin, "to_country": destination}])
    if f.trailers:
        where.append("trailer_types && %(trailers)s::text[]")
        params["trailers"] = f.trailers
    if f.cargo:
        where.append("cargo_types @> %(cargo)s::text[]")
        params["cargo"] = f.cargo
    if f.languages:
        where.append("languages && %(languages)s::text[]")
        params["languages"] = f.languages
    if f.min_load_kg is not None:
        where.append("max_load_kg >= %(min_load)s")
        params["min_load"] = f.min_load_kg
    if f.adr:
        where.append("adr")
    if f.region:
        where.append("home_region ILIKE %(region)s")
        params["region"] = _like(f.region)
    if f.q:
        where.append("search @@ websearch_to_tsquery('simple', %(q)s)")  # websearch syntax never raises on odd input
        params["q"] = f.q
    return " AND ".join(where), params


def run(conn, f: Filters, limit: int, offset: int) -> tuple[int, list[dict]]:
    where, params = where_clause(f)
    total = conn.execute(f"SELECT count(*) AS n FROM companies WHERE {where}", params).fetchone()["n"]
    rank = "ts_rank(search, websearch_to_tsquery('simple', %(q)s))" if f.q else "0::float4"
    rows = conn.execute(
        f"SELECT profile, {rank} AS rank FROM companies WHERE {where} ORDER BY rank DESC, fleet_trucks DESC, name LIMIT %(limit)s OFFSET %(offset)s",
        params | {"limit": limit, "offset": offset},
    ).fetchall()
    return total, rows
