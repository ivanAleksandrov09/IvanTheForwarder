"""Clients, trucks, shipments, invoices, payments, incidents. Owner: B (extend realism here).

TODO(owner B): more varied behaviours (partial payments, seasonal Trakia, Vardar erratic),
               per-route margins, delay incidents, cargo requests that clash with refused_cargo_types.
"""

import random
from dataclasses import dataclass
from datetime import timedelta

from app.schemas import (
    CargoType,
    Client,
    Contact,
    Incident,
    IncidentType,
    Invoice,
    InvoiceStatus,
    Language,
    Money,
    Payment,
    PaymentMethod,
    Severity,
    Shipment,
    ShipmentStatus,
    TrailerType,
    Truck,
    TruckStatus,
)
from app.seed import story
from app.seed.places import loc, road_km
from app.seed.story import NOW, at


@dataclass
class ClientSpec:
    client: Client
    routes: list[tuple[str, str]]
    cargo: CargoType
    n_shipments: int
    pay_delay_mean: float  # days after due date (negative = early)
    pay_delay_sd: float
    cost_ratio: tuple[float, float]  # cost / price
    late_delivery_prob: float = 0.1


def _client(id, name, name_latin, vat, country, city, lang, terms, contact, accepted, refused, notes, years):
    return Client(
        id=id,
        name=name,
        name_latin=name_latin,
        vat_number=vat,
        country=country,
        city=city,
        preferred_language=lang,
        contacts=[contact],
        payment_terms_days=terms,
        accepted_cargo_types=accepted,
        refused_cargo_types=refused,
        notes=notes,
        created_at=at(days=-365 * years),
    )


C = CargoType
SPECS: list[ClientSpec] = [
    ClientSpec(
        _client(story.LATE_PAYER, "Балкан Стил ООД", "Balkan Steel Ltd", "BG204512378", "BG", "Перник", Language.bg, 30,
                Contact(name="Георги Петров", role="Управител", email="g.petrov@balkansteel.bg", phone="+359888123456", language=Language.bg),
                [C.steel, C.general], [C.refrigerated, C.pharma],
                "Плаща след многократни напомняния. Обещава плащане по телефона.", 3),
        [("pernik", "bucharest"), ("pernik", "thessaloniki"), ("sofia", "belgrade")], C.steel, 10, 35, 12, (0.90, 0.96),
    ),
    ClientSpec(
        _client(story.STRICT_CLIENT, "Rhein Logistik GmbH", None, "DE298765431", "DE", "München", Language.en, 45,
                Contact(name="Anna Weber", role="Transport Manager", email="a.weber@rhein-logistik.de", phone="+498912345678", language=Language.en),
                [C.automotive, C.palletized, C.general], [C.adr_dangerous],
                "Framework agreement §7: EUR 150 per started hour beyond the delivery slot, max EUR 600.", 2),
        [("sofia", "munich"), ("plovdiv", "munich")], C.automotive, 9, -2, 2, (0.78, 0.84), 0.0,
    ),
    ClientSpec(
        _client("cli_0003", "Тракия Агро ЕООД", None, "BG123987456", "BG", "Стара Загора", Language.bg, 21,
                Contact(name="Мария Колева", role="Логистика", email="m.koleva@trakia-agro.bg", phone="+359887456123", language=Language.bg),
                [C.grain, C.bulk, C.food], [C.adr_dangerous],
                "Сезонен клиент (жътва юли–октомври).", 4),
        [("stara_zagora", "constanta"), ("stara_zagora", "thessaloniki"), ("stara_zagora", "varna")], C.grain, 8, 4, 5, (0.82, 0.88),
    ),
    ClientSpec(
        _client("cli_0004", "Dunarea Trans SRL", None, "RO31245678", "RO", "București", Language.ro, 30,
                Contact(name="Andrei Popescu", role="Dispecer", email="andrei.popescu@dunareatrans.ro", phone="+40721123456", language=Language.ro),
                [C.general, C.palletized], [],
                None, 2),
        [("bucharest", "sofia"), ("ruse", "vienna")], C.palletized, 8, 16, 9, (0.84, 0.90),
    ),
    ClientSpec(
        _client("cli_0005", "Anadolu Tekstil A.Ş.", None, "TR4561237890", "TR", "Bursa", Language.tr, 30,
                Contact(name="Mehmet Yılmaz", role="Lojistik Müdürü", email="mehmet.yilmaz@anadolutekstil.com.tr", phone="+905321234567", language=Language.tr),
                [C.textile, C.general], [C.food],
                None, 1),
        [("bursa", "sofia"), ("istanbul", "sofia")], C.textile, 7, 1, 3, (0.80, 0.86),
    ),
    ClientSpec(
        _client("cli_0006", "София Фарма АД", None, "BG175001234", "BG", "София", Language.bg, 30,
                Contact(name="Елена Димитрова", role="Мениджър снабдяване", email="e.dimitrova@sofiapharma.bg", phone="+359889654321", language=Language.bg),
                [C.pharma, C.refrigerated], [C.adr_dangerous, C.bulk],
                "Изисква температурен лог 2–8 °C за всяка пратка.", 3),
        [("sofia", "vienna"), ("sofia", "varna")], C.pharma, 8, 0, 1, (0.80, 0.86),
    ),
    ClientSpec(
        _client("cli_0007", "Vardar Food DOOEL", None, "MK4030012345678", "MK", "Скопје", Language.en, 30,
                Contact(name="Bojan Trajkovski", role="Logistics", email="b.trajkovski@vardarfood.mk", phone="+38970123456", language=Language.en),
                [C.food, C.palletized], [],
                None, 1),
        [("skopje", "sofia"), ("sofia", "skopje")], C.food, 6, 9, 18, (0.85, 0.92),
    ),
    ClientSpec(
        _client(story.NEW_CLIENT, "Нова Мебел ООД", None, "BG206998877", "BG", "Пловдив", Language.bg, 14,
                Contact(name="Калин Стоянов", role="Собственик", email="k.stoyanov@novamebel.bg", phone="+359878111222", language=Language.bg),
                [C.furniture], [],
                "Нов клиент от септември 2026.", 0.1),
        [("plovdiv", "milan")], C.furniture, 1, 0, 1, (0.84, 0.88),
    ),
]

CARGO_DETAILS: dict[CargoType, tuple[str, int, int]] = {  # description, min kg, max kg
    C.steel: ("Арматура и стоманени профили", 21000, 24000),
    C.automotive: ("Auto parts (gearboxes), EUR pallets", 9000, 16000),
    C.grain: ("Пшеница, насипно", 23000, 25000),
    C.palletized: ("General cargo, palletized", 8000, 18000),
    C.textile: ("Ready-made garments in cartons", 6000, 12000),
    C.pharma: ("Лекарствени продукти, 2–8 °C", 4000, 9000),
    C.food: ("Packaged food products", 10000, 20000),
    C.furniture: ("Мека мебел, опакована", 5000, 9000),
}

TRUCKS = [
    Truck(id="trk_0001", plate_number="СВ 4821 КН", label="Truck 1", driver_name="Петър Иванов", driver_phone="+359888100001",
          trailer_type=TrailerType.tent, capacity_kg=24000, status=TruckStatus.available, is_own_fleet=True),
    Truck(id="trk_0002", plate_number="СВ 7310 ВР", label="Truck 2", driver_name="Димитър Стоянов", driver_phone="+359888100002",
          trailer_type=TrailerType.mega, capacity_kg=24000, status=TruckStatus.available, is_own_fleet=True),
    Truck(id=story.HERO_TRUCK, plate_number="СВ 1234 АВ", label="Truck 3", driver_name="Николай Георгиев", driver_phone="+359888100003",
          trailer_type=TrailerType.tent, capacity_kg=24000, status=TruckStatus.en_route, is_own_fleet=True,
          current_shipment_id=story.HERO_SHIPMENT),
    Truck(id="trk_0004", plate_number="СВ 5567 ТМ", label="Truck 4 (reefer)", driver_name="Стефан Колев", driver_phone="+359888100004",
          trailer_type=TrailerType.reefer, capacity_kg=22000, status=TruckStatus.en_route, is_own_fleet=True,
          current_shipment_id="shp_0902"),
    Truck(id="trk_0005", plate_number="РВ 9012 ХК", label="Truck 5", driver_name="Христо Димов", driver_phone="+359888100005",
          trailer_type=TrailerType.tent, capacity_kg=24000, status=TruckStatus.en_route, is_own_fleet=True,
          current_shipment_id="shp_0903"),
    Truck(id="trk_0006", plate_number="СВ 3388 МС", label="Partner flatbed", driver_name="Васил Тодоров", driver_phone="+359888100006",
          trailer_type=TrailerType.flatbed, capacity_kg=25000, status=TruckStatus.maintenance, is_own_fleet=False),
]


def _vat(shp: Shipment, net: int) -> int:
    domestic = shp.origin.country == "BG" and shp.destination.country == "BG"
    return round(net * 0.20) if domestic else 0  # international transport: 0% VAT


def _shipment(rng, sid, spec: ClientSpec, route, pickup, truck_id, status, delay_min=0) -> Shipment:
    o, d = route
    km = road_km(o, d)
    transit_h = km / 62 + (km // 650) * 11  # driving + daily rest
    planned = pickup + timedelta(hours=transit_h)
    desc, wmin, wmax = CARGO_DETAILS[spec.cargo]
    price = max(45000, (rng.randint(115, 145) * km) // 1000 * 1000)  # cents, rounded to EUR 10
    cost = int(price * rng.uniform(*spec.cost_ratio))
    seq = int(sid.split("_")[1])
    return Shipment(
        id=sid,
        reference=f"SPD-2026-{seq:04d}",
        client_id=spec.client.id,
        truck_id=truck_id,
        status=status,
        cargo_type=spec.cargo,
        cargo_description=desc,
        weight_kg=rng.randint(wmin, wmax) // 100 * 100,
        pallets=rng.randint(18, 33) if spec.cargo in (C.automotive, C.palletized, C.pharma, C.food) else None,
        origin=loc(o),
        destination=loc(d),
        distance_km=km,
        pickup_planned_at=pickup,
        delivery_planned_at=planned,
        picked_up_at=pickup + timedelta(minutes=rng.randint(-20, 40)) if status != ShipmentStatus.booked else None,
        delivered_at=planned + timedelta(minutes=delay_min) if status == ShipmentStatus.delivered else None,
        price=Money.of(price),
        cost=Money.of(cost),
        cmr_number=f"BG {rng.randint(400000, 499999):07d}",
        created_at=pickup - timedelta(days=rng.randint(1, 5)),
    )


def _invoice_and_payment(rng, shp: Shipment, spec: ClientSpec, force_unpaid=False):
    seq = int(shp.id.split("_")[1])
    issued = shp.delivered_at + timedelta(days=1)
    due = issued + timedelta(days=spec.client.payment_terms_days)
    net = shp.price.amount_minor
    vat = _vat(shp, net)
    inv_id = f"inv_{seq:04d}"
    paid_at = due + timedelta(days=round(rng.gauss(spec.pay_delay_mean, spec.pay_delay_sd)))
    paid_at = max(paid_at, issued + timedelta(days=1))
    paid = not force_unpaid and paid_at <= NOW
    inv = Invoice(
        id=inv_id,
        number=f"{seq:010d}",
        client_id=spec.client.id,
        shipment_ids=[shp.id],
        issued_at=issued,
        due_at=due,
        net=Money.of(net),
        vat=Money.of(vat),
        total=Money.of(net + vat),
        status=InvoiceStatus.paid if paid else InvoiceStatus.issued,
    )
    pay = None
    if paid:
        pay = Payment(
            id=f"pay_{seq:04d}",
            invoice_id=inv_id,
            client_id=spec.client.id,
            amount=inv.total,
            paid_at=paid_at,
            method=PaymentMethod.bank_transfer,
            reference=f"Фактура {inv.number}",
        )
    return inv, pay


def generate(rng: random.Random) -> dict[str, list]:
    shipments: list[Shipment] = []
    invoices: list[Invoice] = []
    payments: list[Payment] = []
    incidents: list[Incident] = []
    seq = 1

    for spec in SPECS:
        days_ago = sorted((rng.uniform(8, 160) for _ in range(spec.n_shipments)), reverse=True)
        if spec.client.id == story.NEW_CLIENT:
            days_ago = [9]
        for k, ago in enumerate(days_ago):
            route = rng.choice(spec.routes)
            delay = rng.randint(70, 300) if rng.random() < spec.late_delivery_prob else rng.randint(-40, 35)
            if spec.client.id == story.STRICT_CLIENT and k in (2, 5):
                delay = (190, 245)[k == 5]
            shp = _shipment(rng, f"shp_{seq:04d}", spec, route, at(days=-ago), rng.choice(["trk_0001", "trk_0002", "trk_0005"]),
                            ShipmentStatus.delivered, delay)
            shipments.append(shp)
            inv, pay = _invoice_and_payment(rng, shp, spec)
            invoices.append(inv)
            if pay:
                payments.append(pay)
            if spec.client.id == story.STRICT_CLIENT and k in (2, 5):
                hours = -(-delay // 60)
                incidents.append(Incident(
                    id=f"inc_{seq:04d}", type=IncidentType.fine, severity=Severity.medium,
                    occurred_at=shp.delivered_at + timedelta(days=3), client_id=spec.client.id, shipment_id=shp.id,
                    truck_id=shp.truck_id, delay_minutes=delay, cost=Money.of(min(60000, hours * 15000)),
                    description=f"Penalty per framework agreement §7: delivery {delay} min after slot ({hours} started hours).",
                ))
            seq += 1

    # --- hero overdue invoice: Balkan Steel, 45 days past due, never paid ---
    spec = SPECS[0]
    shp = _shipment(rng, story.OVERDUE_SHIPMENT, spec, ("pernik", "bucharest"), story.OVERDUE_DUE - timedelta(days=31, hours=20),
                    "trk_0001", ShipmentStatus.delivered, 20)
    shp = shp.model_copy(update={"price": Money.of(348000), "cost": Money.of(331000)})
    shipments.append(shp)
    inv, _ = _invoice_and_payment(rng, shp, spec, force_unpaid=True)
    inv = inv.model_copy(update={"due_at": story.OVERDUE_DUE, "issued_at": story.OVERDUE_DUE - timedelta(days=30)})
    invoices.append(inv)

    # --- other incidents ---
    pharma = next(s for s in shipments if s.client_id == "cli_0006")
    incidents.append(Incident(
        id="inc_0701", type=IncidentType.claim, severity=Severity.high, occurred_at=pharma.delivered_at,
        client_id="cli_0006", shipment_id=pharma.id, truck_id=pharma.truck_id, cost=Money.of(120000),
        description="Temperature excursion to 9.4 °C for 50 min; client claimed EUR 1,200.",
    ))
    vardar = next(s for s in shipments if s.client_id == "cli_0007")
    incidents.append(Incident(
        id="inc_0702", type=IncidentType.documentation_error, severity=Severity.low, occurred_at=vardar.delivered_at,
        client_id="cli_0007", shipment_id=vardar.id, description="Signed CMR copy missing; client delayed payment until received.",
    ))

    # --- active shipments (the "live" situation at DEMO_NOW) ---
    by_id = {s.client.id: s for s in SPECS}
    hero = _shipment(rng, story.HERO_SHIPMENT, by_id[story.STRICT_CLIENT], ("sofia", "munich"), story.HERO_PICKUP,
                     story.HERO_TRUCK, ShipmentStatus.in_transit)
    hero = hero.model_copy(update={
        "delivery_planned_at": story.HERO_SLOT, "eta_at": story.HERO_ETA, "weight_kg": 14200, "pallets": 26,
        "price": Money.of(215000), "cost": Money.of(172000), "cmr_number": "BG 0457812",
    })
    pharma_live = _shipment(rng, "shp_0902", by_id["cli_0006"], ("sofia", "vienna"), at(hours=-9), "trk_0004", ShipmentStatus.in_transit)
    pharma_live = pharma_live.model_copy(update={"eta_at": pharma_live.delivery_planned_at - timedelta(minutes=20)})
    dunarea_live = _shipment(rng, "shp_0903", by_id["cli_0004"], ("bucharest", "sofia"), at(hours=-6), "trk_0005", ShipmentStatus.in_transit)
    dunarea_live = dunarea_live.model_copy(update={"eta_at": dunarea_live.delivery_planned_at + timedelta(minutes=25)})
    booked = _shipment(rng, "shp_0904", by_id[story.NEW_CLIENT], ("plovdiv", "milan"), at(days=1, hours=-2), "trk_0002", ShipmentStatus.booked)
    shipments += [hero, pharma_live, dunarea_live, booked]

    return {
        "clients": [s.client for s in SPECS],
        "trucks": TRUCKS,
        "shipments": shipments,
        "invoices": invoices,
        "payments": payments,
        "incidents": incidents,
    }
