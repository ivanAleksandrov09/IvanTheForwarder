"""THE schema gate. Fails if seed data, connector output or the committed OpenAPI spec drift from app.schemas.
Runs in CI on every PR (and locally with `npm test`).
"""

import json
from datetime import datetime

import pytest

from app.core.config import REPO_ROOT, get_settings
from app.repository import SeedStore
from app.repository.seed_store import FEED_MODELS
from app.schemas import COLLECTIONS, SEED_COLLECTIONS, ConnectorEnvelope, SourceType

SEED = SeedStore(get_settings().seed_dir)


@pytest.mark.parametrize("name", SEED_COLLECTIONS)
def test_seed_file_exists_and_validates(name):
    path = SEED.seed_dir / f"{name}.json"
    assert path.exists(), f"missing {path} - run `npm run seed`"
    items = SEED.load(name)  # raises ValidationError on any bad row
    key = COLLECTIONS[name][1]
    ids = [getattr(i, key) for i in items]
    assert len(ids) == len(set(ids)), f"duplicate ids in {name}"


def test_feeds_are_registered_and_validate():
    for feed in SEED.feed_names():
        assert feed in FEED_MODELS, f"feeds/{feed}.json has no entry in seed_store.FEED_MODELS"
        SEED.load_feed(feed, FEED_MODELS[feed])


def test_referential_integrity():
    ids = {name: {getattr(i, COLLECTIONS[name][1]) for i in SEED.load(name)} for name in SEED_COLLECTIONS}
    refs = {"client_id": "clients", "truck_id": "trucks", "shipment_id": "shipments", "invoice_id": "invoices", "email_id": "emails"}
    for name in SEED_COLLECTIONS:
        for item in SEED.load(name):
            for field, target in refs.items():
                value = getattr(item, field, None)
                if value is not None:
                    assert value in ids[target], f"{name}/{getattr(item, 'id', '?')}: {field}={value} not found in {target}"
            for sid in getattr(item, "shipment_ids", []):
                assert sid in ids["shipments"]
            for did in getattr(item, "attachment_document_ids", []):
                assert did in ids["documents"]


def test_seed_is_utf8_and_not_transliterated():
    raw = (SEED.seed_dir / "clients.json").read_text(encoding="utf-8")
    assert "Балкан Стил ООД" in raw, "Cyrillic must be stored as-is (ensure_ascii=False, no transliteration)"


def test_timestamps_are_utc_z():
    raw = json.loads((SEED.seed_dir / "shipments.json").read_text(encoding="utf-8"))
    for row in raw:
        assert row["pickup_planned_at"].endswith("Z")
        datetime.fromisoformat(row["pickup_planned_at"])


def test_every_connector_emits_valid_envelopes(client):
    from app.deps import get_connectors

    for source, connector in get_connectors().items():
        if connector.mode != "mock":
            continue
        for env in connector.fetch():
            assert isinstance(env, ConnectorEnvelope)
            assert env.source == source
            ConnectorEnvelope.model_validate(env.model_dump(mode="json"))  # JSON round-trip


def test_openapi_spec_is_up_to_date():
    from app.main import app

    committed = json.loads((REPO_ROOT / "shared" / "openapi.json").read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(app.openapi())), "schemas changed: run `npm run gen:types` and commit"


def test_email_connector_source_is_registered(client):
    from app.deps import get_connectors

    assert SourceType.email in get_connectors()
