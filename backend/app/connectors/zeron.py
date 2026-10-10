"""Zeron V/4 connector: clients (counterparties), trucks (vehicles), loads (orders), invoices and GPS positions. Owner: A.

ASSUMPTION: Zeron's real API is not publicly documented. The paths and field names below are a GUESS for a typical REST + JSON
ERP. The mock (CONNECTOR_ERP=zeron_mock) answers them from data/mock/zeron.json. When Elite Software sends the real
documentation, change only PATHS, ZeronApi._live and the `map_*` functions.

Sample requests (live: `Authorization: Bearer <ZERON_TOKEN>`, response body `{"items": [...]}`):
  GET {ZERON_URL}/api/v1/counterparties                           clients, fetched in full (reference data)
  GET {ZERON_URL}/api/v1/vehicles                                 trucks, fetched in full (reference data)
  GET {ZERON_URL}/api/v1/orders?modifiedSince=2026-10-15T07:00:00Z     loads
  GET {ZERON_URL}/api/v1/invoices?modifiedSince=2026-10-15T07:00:00Z   invoices
  GET {ZERON_URL}/api/v1/vehicles/positions?modifiedSince=...          GPS positions

Rules: clients and trucks already known (matched by VAT number / plate) are never overwritten; orders, invoices and
positions are upserted by stable id, so repeated syncs are idempotent. Rows that fail validation are skipped and logged.
"""

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

import httpx

from app.connectors.base import BaseConnector
from app.core import clock
from app.core.config import Settings
from app.core.ids import stable_id
from app.repository import Repository
from app.schemas import (
    CargoType,
    Client,
    ConnectorEnvelope,
    ConnectorHealth,
    Contact,
    GpsPing,
    Invoice,
    InvoiceStatus,
    Language,
    Location,
    Money,
    Shipment,
    ShipmentStatus,
    SourceType,
    TrailerType,
    Truck,
    TruckStatus,
)

log = logging.getLogger("forwarder.zeron")

PATHS = {
    "counterparties": "/api/v1/counterparties",
    "vehicles": "/api/v1/vehicles",
    "orders": "/api/v1/orders",
    "invoices": "/api/v1/invoices",
    "positions": "/api/v1/vehicles/positions",
}
ORDER_STATUS = {"QUOTED": ShipmentStatus.quoted, "CONFIRMED": ShipmentStatus.booked, "IN_TRANSIT": ShipmentStatus.in_transit,
                "DELIVERED": ShipmentStatus.delivered, "CANCELLED": ShipmentStatus.cancelled}
INVOICE_STATUS = {"DRAFT": InvoiceStatus.draft, "ISSUED": InvoiceStatus.issued, "PARTIAL": InvoiceStatus.partially_paid,
                  "PAID": InvoiceStatus.paid, "CANCELLED": InvoiceStatus.cancelled}
VEHICLE_STATUS = {"FREE": TruckStatus.available, "LOADING": TruckStatus.loading, "ON_ROUTE": TruckStatus.en_route,
                  "UNLOADING": TruckStatus.unloading, "SERVICE": TruckStatus.maintenance}


def _dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _money(amount: str, currency: str) -> Money:
    return Money.of(int((Decimal(str(amount)) * 100).to_integral_value()), currency or "EUR")


def _key(value: str | None) -> str:
    return "".join((value or "").upper().split())  # VAT numbers and plates compared without spaces/case


def _enum(enum_cls, value, default):
    try:
        return enum_cls(str(value).lower())
    except ValueError:
        return default


class ZeronApi:
    """The request layer: the only place that knows paths, auth and the response envelope."""

    def __init__(self, settings: Settings, mock: bool):
        self.s, self.mock = settings, mock
        self.requests: list[str] = []  # the sample requests sent (or simulated), newest last
        self._data: dict | None = None

    def get(self, resource: str, since: datetime | None = None) -> list[dict]:
        params = {"modifiedSince": _iso(since)} if since else {}
        line = f"GET {PATHS[resource]}" + (f"?modifiedSince={params['modifiedSince']}" if params else "")
        self.requests = [*self.requests, line][-50:]
        log.info("zeron %s %s", "mock" if self.mock else "live", line)
        return self._answer_mock(resource, since) if self.mock else self._live(resource, params)

    def _answer_mock(self, resource: str, since: datetime | None) -> list[dict]:
        if self._data is None:
            self._data = json.loads((self.s.data_dir / "mock" / "zeron.json").read_text(encoding="utf-8"))
        return [r for r in self._data.get(resource, []) if since is None or _dt(r["modified"]) > since]

    def _live(self, resource: str, params: dict) -> list[dict]:
        if not self.s.zeron_url:
            raise ValueError("ZERON_URL is required when CONNECTOR_ERP=zeron")
        headers = {"Accept": "application/json"}
        if self.s.zeron_token:
            headers["Authorization"] = f"Bearer {self.s.zeron_token}"
        try:
            response = httpx.get(self.s.zeron_url.rstrip("/") + PATHS[resource], params=params, headers=headers, timeout=20.0)
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RuntimeError(f"Zeron request failed: {exc}") from exc
        items = body.get("items") if isinstance(body, dict) else body
        if not isinstance(items, list):
            raise RuntimeError("Zeron response must be a list or {'items': [...]}")
        return items


# ---- Zeron JSON -> our schema (the only code that knows Zeron's field names)
def map_client(row: dict, client_id: str) -> Client:
    lang = _enum(Language, row.get("language"), Language.bg)
    contact = Contact(name=row.get("contactName") or row["name"], email=row.get("email"), phone=row.get("phone"), language=lang)
    return Client(id=client_id, name=row["name"], vat_number=row.get("vatNumber"), country=row["country"], city=row["city"],
                  preferred_language=lang, contacts=[contact], payment_terms_days=int(row.get("paymentTermDays", 30)), created_at=clock.now())


def map_truck(row: dict, truck_id: str) -> Truck:
    return Truck(id=truck_id, plate_number=row["plate"], label=row.get("label") or row["plate"], driver_name=row.get("driver"),
                 driver_phone=row.get("driverPhone"), trailer_type=_enum(TrailerType, row.get("trailerType"), TrailerType.tent),
                 capacity_kg=int(row["capacityKg"]), status=VEHICLE_STATUS.get(str(row.get("status")).upper(), TruckStatus.available),
                 is_own_fleet=bool(row.get("own", True)))


def _place(p: dict) -> Location:
    return Location(city=p["city"], country=p["country"], lat=p.get("lat"), lon=p.get("lon"))


def map_shipment(row: dict, shipment_id: str, client_id: str, truck_id: str | None) -> Shipment:
    def when(key):
        return _dt(row[key]) if row.get(key) else None

    cost = row.get("cost")
    return Shipment(
        id=shipment_id, reference=row["number"], client_id=client_id, truck_id=truck_id,
        status=ORDER_STATUS[str(row["status"]).upper()], cargo_type=_enum(CargoType, row.get("cargoType"), CargoType.general),
        cargo_description=row.get("cargo") or "", weight_kg=int(row.get("weightKg", 0)), pallets=row.get("pallets"),
        origin=_place(row["from"]), destination=_place(row["to"]), distance_km=float(row.get("distanceKm", 0)),
        pickup_planned_at=_dt(row["pickupPlanned"]), delivery_planned_at=_dt(row["deliveryPlanned"]), picked_up_at=when("pickedUp"),
        delivered_at=when("delivered"), eta_at=when("eta"), price=_money(row["price"]["amount"], row["price"]["currency"]),
        cost=_money(cost["amount"], cost["currency"]) if cost else None, cmr_number=row.get("cmr"), created_at=_dt(row["created"]),
    )


def map_invoice(row: dict, invoice_id: str, client_id: str, shipment_ids: list[str]) -> Invoice:
    cur = row.get("currency", "EUR")
    return Invoice(id=invoice_id, number=row["number"], client_id=client_id, shipment_ids=shipment_ids, issued_at=_dt(row["issueDate"]),
                   due_at=_dt(row["dueDate"]), net=_money(row["net"], cur), vat=_money(row["vat"], cur), total=_money(row["total"], cur),
                   status=INVOICE_STATUS[str(row["status"]).upper()])


def map_ping(row: dict, ping_id: str, truck_id: str) -> GpsPing:
    return GpsPing(id=ping_id, truck_id=truck_id, recorded_at=_dt(row["time"]), lat=float(row["lat"]), lon=float(row["lon"]),
                   speed_kmh=max(0.0, float(row.get("speedKmh", 0))), heading_deg=row.get("heading"))


class ZeronConnector(BaseConnector):
    name = "erp.zeron"
    source = SourceType.erp
    mode = "live"
    description = "Reads clients, trucks, loads, invoices and GPS positions from Zeron V/4 (assumed API; see module docstring)."

    def __init__(self, settings: Settings, repo_provider: Callable[[], Repository], mock: bool = False):
        super().__init__()
        self.settings = settings
        self.repo_provider = repo_provider
        self.api = ZeronApi(settings, mock)
        self.mode = "mock" if mock else "live"
        self.skipped: list[str] = []  # rows that failed validation in the last fetch

    def health(self) -> ConnectorHealth:
        return ConnectorHealth.ok if self.api.mock or self.settings.zeron_url else ConnectorHealth.disabled

    def fetch(self, since: datetime | None = None) -> list[ConnectorEnvelope]:
        repo = self.repo_provider()  # read-only: used to match what we already know
        known_clients = {c.id for c in repo.clients.list()}
        client_by_vat = {_key(c.vat_number): c.id for c in repo.clients.list() if c.vat_number}
        known_trucks = {t.id for t in repo.trucks.list()}
        truck_by_plate = {_key(t.plate_number): t.id for t in repo.trucks.list()}
        out: list[ConnectorEnvelope] = []
        self.skipped = []

        def add(what: str, row: dict, build: Callable[[], object]) -> None:
            try:
                out.append(self.wrap(build(), external_id=str(row.get("id"))))
            except (ValueError, KeyError, TypeError) as exc:
                self.skipped.append(f"{what} {row.get('id')}: {exc}")
                log.warning("zeron: skipped %s %s: %s", what, row.get("id"), exc)

        def fresh(row: dict) -> bool:
            return since is None or _dt(row["modified"]) > since

        client_ids: dict[str, str] = {}
        for row in self.api.get("counterparties"):
            cid = client_by_vat.get(_key(row.get("vatNumber"))) or stable_id("cli", "zeron", row["id"])
            client_ids[row["id"]] = cid
            if cid not in known_clients and fresh(row):
                add("counterparty", row, lambda row=row, cid=cid: map_client(row, cid))
        truck_ids: dict[str, str] = {}
        for row in self.api.get("vehicles"):
            tid = truck_by_plate.get(_key(row.get("plate"))) or stable_id("trk", "zeron", row["id"])
            truck_ids[row["id"]] = tid
            if tid not in known_trucks and fresh(row):
                add("vehicle", row, lambda row=row, tid=tid: map_truck(row, tid))
        for row in self.api.get("orders", since):
            if row.get("counterpartyId") in client_ids:
                add("order", row, lambda row=row: map_shipment(
                    row, stable_id("shp", "zeron", row["id"]), client_ids[row["counterpartyId"]], truck_ids.get(row.get("vehicleId"))))
        for row in self.api.get("invoices", since):
            if row.get("counterpartyId") in client_ids:
                add("invoice", row, lambda row=row: map_invoice(
                    row, stable_id("inv", "zeron", row["id"]), client_ids[row["counterpartyId"]],
                    [stable_id("shp", "zeron", o) for o in row.get("orderIds", [])]))
        for row in self.api.get("positions", since):
            if row.get("vehicleId") in truck_ids:
                add("position", row, lambda row=row: map_ping(row, stable_id("gps", "zeron", row["id"]), truck_ids[row["vehicleId"]]))
        return out
