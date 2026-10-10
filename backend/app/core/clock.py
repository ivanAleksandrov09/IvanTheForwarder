"""The ONLY place that knows what "now" is. Never call datetime.now() elsewhere.

In CLOCK_MODE=fixed the app lives at DEMO_NOW, so the seeded story (overdue invoices,
late trucks) looks identical on every machine and every rehearsal.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.core.config import get_settings

LOCAL_TZ = ZoneInfo("Europe/Sofia")  # display only; storage is always UTC


def now() -> datetime:
    s = get_settings()
    if s.clock_mode == "fixed":
        return s.demo_now.astimezone(UTC)
    return datetime.now(UTC)


def to_local(dt: datetime) -> datetime:
    return dt.astimezone(LOCAL_TZ)
