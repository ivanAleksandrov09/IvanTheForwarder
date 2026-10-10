"""Reads/writes the committed seed files. The only code allowed to open data/seed/*.

data/seed/<collection>.json      base dataset, loaded into the DB on startup / reset
data/seed/feeds/<feed>.json      "live" items that mock connectors deliver on sync (not preloaded)
"""

import json
from pathlib import Path
from typing import TypeVar

from app.schemas import COLLECTIONS, ContractModel, Email

T = TypeVar("T", bound=ContractModel)

# feed file name -> model. Every file in data/seed/feeds/ must be registered here (checked by tests).
FEED_MODELS: dict[str, type[ContractModel]] = {
    "email_inbox": Email,
    # TODO(owner A): "documents_inbox": Document, "gps_live": GpsPing, "erp_invoices": Invoice, ...
}


class SeedStore:
    def __init__(self, seed_dir: Path):
        self.seed_dir = seed_dir

    def _read(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def load(self, collection: str) -> list[ContractModel]:
        model, _ = COLLECTIONS[collection]
        return [model.model_validate(row) for row in self._read(self.seed_dir / f"{collection}.json")]

    def load_feed(self, feed: str, model: type[T]) -> list[T]:
        return [model.model_validate(row) for row in self._read(self.seed_dir / "feeds" / f"{feed}.json")]

    def feed_names(self) -> list[str]:
        return sorted(p.stem for p in (self.seed_dir / "feeds").glob("*.json"))

    # ---- writing (seed generator only) ----
    def write(self, name: str, items: list[ContractModel], feed: bool = False) -> Path:
        path = self.seed_dir / ("feeds" if feed else "") / f"{name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = [i.model_dump(mode="json") for i in items]
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        return path
