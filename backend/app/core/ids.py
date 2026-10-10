"""ID generation. Format: <prefix>_<4-32 lowercase alphanumerics>, e.g. cli_0001, drf_3f9a1c0b7e2d4a51."""

import hashlib
import uuid

PREFIXES = {
    "client": "cli",
    "truck": "trk",
    "gps_ping": "gps",
    "shipment": "shp",
    "email": "eml",
    "document": "doc",
    "invoice": "inv",
    "payment": "pay",
    "incident": "inc",
    "call_log": "cal",
    "event": "evt",
    "draft": "drf",
    "envelope": "env",
}


def new_id(prefix: str) -> str:
    """Random ID for runtime-created objects."""
    assert prefix in PREFIXES.values(), f"unknown id prefix {prefix!r}"
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def stable_id(prefix: str, *parts: str) -> str:
    """Deterministic ID from content, for idempotent detection (same event -> same ID)."""
    assert prefix in PREFIXES.values(), f"unknown id prefix {prefix!r}"
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"
