"""Generate data/seed/ deterministically. Run from backend/: `uv run python -m app.seed.generate`. Owner: lead.

Same SEED -> byte-identical output, so seed diffs in PRs are reviewable.
"""

import random
import sys

from app.core.config import get_settings
from app.repository import SeedStore
from app.schemas import COLLECTIONS, SEED_COLLECTIONS
from app.seed import gen_business, gen_comms, gen_tracking, story


def build() -> tuple[dict[str, list], dict[str, list]]:
    rng = random.Random(story.SEED)
    data: dict[str, list] = {}
    data |= gen_business.generate(rng)
    data |= gen_tracking.generate(rng)
    comms = gen_comms.generate(rng, data)
    feeds = comms.pop("feeds")
    data |= comms

    missing = set(SEED_COLLECTIONS) - set(data)
    if missing:
        raise SystemExit(f"generator did not produce: {sorted(missing)}")
    for name, items in data.items():  # every item must be an instance of the canonical model
        model, key = COLLECTIONS[name]
        ids = [getattr(i, key) for i in items]
        assert all(isinstance(i, model) for i in items), f"{name}: wrong model type"
        assert len(ids) == len(set(ids)), f"{name}: duplicate ids"
    return data, feeds


def main() -> None:
    data, feeds = build()
    store = SeedStore(get_settings().seed_dir)
    for name in SEED_COLLECTIONS:
        store.write(name, sorted(data[name], key=lambda o: getattr(o, COLLECTIONS[name][1])))
    for name, items in feeds.items():
        store.write(name, items, feed=True)
    summary = ", ".join(f"{n}={len(data[n])}" for n in SEED_COLLECTIONS)
    print(f"seed written to {store.seed_dir}: {summary}; feeds: {', '.join(f'{k}={len(v)}' for k, v in feeds.items())}")
    print("NOTE: delete data/runtime/app.db (or POST /api/system/reset) to load the new seed.", file=sys.stderr)


if __name__ == "__main__":
    main()
