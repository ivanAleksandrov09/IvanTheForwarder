from datetime import UTC, datetime, timedelta

from app.repository import Repository
from app.risk.scoring import compute_profile
from app.schemas import (
    CargoType,
    Client,
    Direction,
    Email,
    Incident,
    IncidentType,
    Language,
    Location,
    Money,
    Severity,
    Shipment,
    ShipmentStatus,
)

NOW = datetime(2026, 10, 15, 7, 30, tzinfo=UTC)


def _client(**overrides):
    values = {
        "id": "cli_test1",
        "name": "Test Client",
        "country": "BG",
        "city": "Sofia",
        "preferred_language": Language.en,
        "payment_terms_days": 30,
        "created_at": NOW - timedelta(days=365),
    }
    values.update(overrides)
    return Client(**values)


def _shipment(shipment_id, **overrides):
    values = {
        "id": shipment_id,
        "reference": f"SPD-{shipment_id}",
        "client_id": "cli_test1",
        "status": ShipmentStatus.delivered,
        "cargo_type": CargoType.general,
        "cargo_description": "General freight",
        "weight_kg": 1000,
        "origin": Location(city="Sofia", country="BG"),
        "destination": Location(city="Bucharest", country="RO"),
        "distance_km": 300,
        "pickup_planned_at": NOW - timedelta(days=3),
        "delivery_planned_at": NOW - timedelta(days=2),
        "delivered_at": NOW - timedelta(days=2),
        "price": Money.of(100_000),
        "cost": Money.of(80_000),
        "created_at": NOW - timedelta(days=4),
    }
    values.update(overrides)
    return Shipment(**values)


def _factor(profile, code):
    return next(factor for factor in profile.factors if factor.code.value == code)


def _assert_explained(factor):
    assert factor.explanation
    assert factor.evidence


def test_low_margin_reports_lane_margin_and_shipment_evidence():
    repo = Repository(":memory:")
    repo.clients.upsert(_client())
    repo.shipments.upsert_many(
        [
            _shipment("shp_test1", price=Money.of(100_000), cost=Money.of(95_000)),
            _shipment("shp_test2", price=Money.of(100_000), cost=Money.of(94_000)),
        ]
    )

    profile = compute_profile("cli_test1", repo, NOW)
    factor = _factor(profile, "low_margin")

    assert profile.metrics.avg_margin_pct == 5.5
    assert "5.5%" in factor.explanation
    assert "Sofia → Bucharest" in factor.explanation
    assert {e.entity_id for e in factor.evidence} == {"shp_test1", "shp_test2"}
    _assert_explained(factor)


def test_damage_claims_aggregate_incidents_costs_and_evidence():
    repo = Repository(":memory:")
    repo.clients.upsert(_client())
    repo.incidents.upsert_many(
        [
            Incident(
                id="inc_test1",
                type=IncidentType.damage,
                severity=Severity.medium,
                occurred_at=NOW - timedelta(days=10),
                client_id="cli_test1",
                description="Cargo packaging damaged",
                cost=Money.of(12_500),
            ),
            Incident(
                id="inc_test2",
                type=IncidentType.claim,
                severity=Severity.high,
                occurred_at=NOW - timedelta(days=5),
                client_id="cli_test1",
                description="Customer claim",
            ),
        ]
    )

    factor = _factor(compute_profile("cli_test1", repo, NOW), "damage_claims")

    assert "2 damage/claim incident(s)" in factor.explanation
    assert "EUR 125.00" in factor.explanation
    assert {e.entity_id for e in factor.evidence} == {"inc_test1", "inc_test2"}
    _assert_explained(factor)


def test_cargo_restrictions_only_flag_conflicting_shipments():
    repo = Repository(":memory:")
    repo.clients.upsert(
        _client(
            accepted_cargo_types=[CargoType.grain],
            refused_cargo_types=[CargoType.adr_dangerous],
        )
    )
    repo.shipments.upsert_many(
        [
            _shipment("shp_test1", cargo_type=CargoType.grain),
            _shipment("shp_test2", cargo_type=CargoType.adr_dangerous),
        ]
    )

    factor = _factor(compute_profile("cli_test1", repo, NOW), "cargo_restrictions")

    assert "1 of 2 shipment(s)" in factor.explanation
    assert "adr_dangerous: 1" in factor.explanation
    assert [e.entity_id for e in factor.evidence] == ["shp_test2"]
    _assert_explained(factor)


def test_delay_sensitivity_uses_delay_incidents_and_complaint_emails():
    repo = Repository(":memory:")
    repo.clients.upsert(_client())
    repo.incidents.upsert(
        Incident(
            id="inc_test1",
            type=IncidentType.delay,
            severity=Severity.medium,
            occurred_at=NOW - timedelta(days=2),
            client_id="cli_test1",
            description="Late delivery",
            delay_minutes=90,
        )
    )
    repo.emails.upsert(
        Email(
            id="eml_test1",
            mailbox="office@example.com",
            direction=Direction.inbound,
            from_address="client@example.com",
            to_addresses=["office@example.com"],
            subject="Late delivery complaint",
            body_text="The delivery missed our agreed slot.",
            sent_at=NOW - timedelta(days=1),
            client_id="cli_test1",
            labels=["complaint"],
        )
    )

    factor = _factor(compute_profile("cli_test1", repo, NOW), "delay_sensitivity")

    assert "1 delay incident(s)" in factor.explanation
    assert "1 additional penalty/complaint email(s)" in factor.explanation
    assert {e.entity_id for e in factor.evidence} == {"inc_test1", "eml_test1"}
    _assert_explained(factor)


def test_slow_communication_uses_explicit_thread_reply_pairs():
    repo = Repository(":memory:")
    repo.clients.upsert(_client())
    repo.emails.upsert_many(
        [
            Email(
                id="eml_test1",
                thread_id="thread_test1",
                mailbox="office@example.com",
                direction=Direction.outbound,
                from_address="office@example.com",
                to_addresses=["client@example.com"],
                subject="Delivery update",
                body_text="Please confirm receipt.",
                sent_at=NOW - timedelta(days=5),
                client_id="cli_test1",
            ),
            Email(
                id="eml_test2",
                thread_id="thread_test1",
                mailbox="office@example.com",
                direction=Direction.inbound,
                from_address="client@example.com",
                to_addresses=["office@example.com"],
                subject="RE: Delivery update",
                body_text="Confirmed.",
                sent_at=NOW - timedelta(days=2),
                client_id="cli_test1",
            ),
        ]
    )

    profile = compute_profile("cli_test1", repo, NOW)
    factor = _factor(profile, "slow_communication")

    assert profile.metrics.avg_email_response_hours == 72
    assert "72.0 hours" in factor.explanation
    assert {e.entity_id for e in factor.evidence} == {"eml_test1", "eml_test2"}
    _assert_explained(factor)
