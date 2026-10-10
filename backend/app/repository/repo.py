"""Data-access layer. The ONLY code that touches the database. Owner: lead.

Storage: one SQLite table of JSON documents keyed by (collection, id). Every write and every read
goes through the Pydantic model, so invalid data can neither get in nor come out.
Query by loading + filtering in Python; fine at hackathon scale (thousands of rows).
"""

from __future__ import annotations  # Collection.list() shadows the builtin inside the class body

import json
import sqlite3
import threading
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, Generic, TypeVar

from app.core import clock
from app.core.errors import NotFoundError
from app.schemas import (
    COLLECTIONS,
    PAYLOAD_COLLECTION,
    CallLog,
    Client,
    ContractModel,
    Document,
    DomainEvent,
    DraftMessage,
    Email,
    GpsPing,
    Incident,
    Invoice,
    PayloadType,
    Payment,
    RiskProfile,
    Shipment,
    Truck,
)

T = TypeVar("T", bound=ContractModel)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS docs (
    collection TEXT NOT NULL,
    id         TEXT NOT NULL,
    data       TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (collection, id)
);
"""


class _Db:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(_SCHEMA)
        self.lock = threading.RLock()


class Collection(Generic[T]):
    def __init__(self, db: _Db, name: str, model: type[T], key: str):
        self._db, self.name, self.model, self.key = db, name, model, key

    def _load(self, raw: str) -> T:
        return self.model.model_validate_json(raw)

    def get(self, id: str) -> T | None:
        with self._db.lock:
            row = self._db.conn.execute(
                "SELECT data FROM docs WHERE collection=? AND id=?", (self.name, id)
            ).fetchone()
        return self._load(row[0]) if row else None

    def require(self, id: str) -> T:
        obj = self.get(id)
        if obj is None:
            raise NotFoundError(f"{self.name}/{id} not found")
        return obj

    def list(self, where: Callable[[T], bool] | None = None, **equals: Any) -> list[T]:
        """list(client_id="cli_0001") or list(where=lambda s: s.weight_kg > 1000). Ordered by id."""
        with self._db.lock:
            rows = self._db.conn.execute(
                "SELECT data FROM docs WHERE collection=? ORDER BY id", (self.name,)
            ).fetchall()
        items = [self._load(r[0]) for r in rows]
        if equals:
            items = [i for i in items if all(getattr(i, k) == v for k, v in equals.items())]
        if where:
            items = [i for i in items if where(i)]
        return items

    def upsert(self, obj: T) -> T:
        return self.upsert_many([obj])[0]

    def upsert_many(self, objs: Iterable[T]) -> list[T]:
        validated = []
        for obj in objs:
            if not isinstance(obj, self.model):
                raise TypeError(f"{self.name} accepts {self.model.__name__}, got {type(obj).__name__}")
            # re-validate: catches objects built with model_copy(update=...) which skips validation
            validated.append(self.model.model_validate(obj.model_dump()))
        stamp = clock.now().isoformat()
        with self._db.lock, self._db.conn:
            self._db.conn.executemany(
                "INSERT INTO docs(collection,id,data,updated_at) VALUES(?,?,?,?) "
                "ON CONFLICT(collection,id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at",
                [(self.name, getattr(o, self.key), o.model_dump_json(), stamp) for o in validated],
            )
        return validated

    def delete(self, id: str) -> None:
        with self._db.lock, self._db.conn:
            self._db.conn.execute("DELETE FROM docs WHERE collection=? AND id=?", (self.name, id))

    def count(self) -> int:
        with self._db.lock:
            return self._db.conn.execute("SELECT COUNT(*) FROM docs WHERE collection=?", (self.name,)).fetchone()[0]

    def clear(self) -> None:
        with self._db.lock, self._db.conn:
            self._db.conn.execute("DELETE FROM docs WHERE collection=?", (self.name,))


class Repository:
    """Typed access to every collection: repo.clients.get("cli_0001"), repo.drafts.upsert(d), ..."""

    def __init__(self, db_path: Path | str):
        db = _Db(db_path)
        c = lambda name: Collection(db, name, *COLLECTIONS[name])  # noqa: E731
        self.clients: Collection[Client] = c("clients")
        self.trucks: Collection[Truck] = c("trucks")
        self.gps_pings: Collection[GpsPing] = c("gps_pings")
        self.shipments: Collection[Shipment] = c("shipments")
        self.emails: Collection[Email] = c("emails")
        self.documents: Collection[Document] = c("documents")
        self.invoices: Collection[Invoice] = c("invoices")
        self.payments: Collection[Payment] = c("payments")
        self.incidents: Collection[Incident] = c("incidents")
        self.call_logs: Collection[CallLog] = c("call_logs")
        self.events: Collection[DomainEvent] = c("events")
        self.drafts: Collection[DraftMessage] = c("drafts")
        self.risk_profiles: Collection[RiskProfile] = c("risk_profiles")

    def collection(self, name: str) -> Collection:
        return getattr(self, name)

    def collection_for_payload(self, payload_type: PayloadType) -> Collection:
        return self.collection(PAYLOAD_COLLECTION[payload_type])

    def is_empty(self) -> bool:
        return self.clients.count() == 0

    def wipe(self) -> None:
        for name in COLLECTIONS:
            self.collection(name).clear()

    def stats(self) -> dict[str, int]:
        return {name: self.collection(name).count() for name in COLLECTIONS}


def load_seed_into(repo: Repository, seed) -> dict[str, int]:
    """Load every seed collection into the repository (idempotent upsert)."""
    from app.schemas import SEED_COLLECTIONS

    loaded = {}
    for name in SEED_COLLECTIONS:
        items = seed.load(name)
        repo.collection(name).upsert_many(items)
        loaded[name] = len(items)
    return loaded


def dumps(obj: ContractModel) -> str:  # helper for logs/debug
    return json.dumps(obj.model_dump(mode="json"), ensure_ascii=False)
