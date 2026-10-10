"""The demo storyline. These IDs are referenced by docs/DEMO_SCRIPT.md and tests: do not renumber. Owner: lead.

At DEMO_NOW (Thu 15 Oct 2026, 10:30 Sofia time):
1. Truck 3 (СВ 1234 АВ, Николай Георгиев) carries Rhein Logistik's gearboxes Sofia -> München.
   It has been stuck 3h40m in the queue at Batrovci (RS/HR border). Projected ETA 10:20 local vs the
   binding 08:00 slot tomorrow -> 2h20m late. Rhein fined us twice before for late slots.
   => event shipment_delayed -> profile says "strict, fines" -> formal/apologetic EN heads-up drafted.
2. Балкан Стил ООД has invoice 0000000801 (EUR 3,480.00) 45 days overdue, after two reminders and a
   broken promise to pay. Chronic late payer (~35 days average).
   => event invoice_overdue -> profile says "pays late, overdue now" -> firm BG reminder drafted.
3. "Sync inbox" delivers new mail, incl. Balkan Steel asking for a NEW quote while still overdue.
"""

from datetime import datetime, timedelta

from app.core.config import DEFAULT_DEMO_NOW

SEED = 20261015
NOW = datetime.fromisoformat(DEFAULT_DEMO_NOW)

OUR_MAILBOX = "office@vitosha-spedition.bg"
OUR_DOMAIN = "vitosha-spedition.bg"

# clients
LATE_PAYER = "cli_0001"  # Балкан Стил ООД
STRICT_CLIENT = "cli_0002"  # Rhein Logistik GmbH
NEW_CLIENT = "cli_0008"  # Нова Мебел ООД (insufficient history)

# hero shipment / truck (delay heads-up)
HERO_TRUCK = "trk_0003"
HERO_SHIPMENT = "shp_0901"
HERO_PICKUP = NOW - timedelta(hours=15, minutes=40)
HERO_SLOT = NOW + timedelta(hours=22, minutes=30)  # 16 Oct 08:00 Europe/Berlin
HERO_ETA = NOW + timedelta(hours=24, minutes=50)  # 2h20m late
HERO_STUCK_SINCE = NOW - timedelta(hours=3, minutes=40)

# hero overdue invoice (payment reminder)
OVERDUE_SHIPMENT = "shp_0801"
OVERDUE_INVOICE = "inv_0801"
OVERDUE_DUE = NOW - timedelta(days=45)


def at(days: float = 0, hours: float = 0, minutes: float = 0) -> datetime:
    """Relative to NOW. at(days=-3) = three days ago."""
    return NOW + timedelta(days=days, hours=hours, minutes=minutes)
