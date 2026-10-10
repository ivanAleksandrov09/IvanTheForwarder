"""GPS pings for trucks. Owner: A.

Each active truck follows timed keypoints; pings every 20 min are interpolated between them.
A keypoint repeated at a later time = truck stationary (border queue, rest, loading).
TODO(owner A): 7-day history for all trucks, realistic road waypoints, a feeds/gps_live.json that the
               mock GPS connector replays so the hero truck "moves" during the demo.
"""

import math
import random
from datetime import datetime, timedelta

from app.schemas import GpsPing
from app.seed import story
from app.seed.places import CITIES, KNOWN_PLACES, haversine_km
from app.seed.story import NOW

STEP = timedelta(minutes=20)


def _p(key: str) -> tuple[float, float]:
    if key in CITIES:
        return CITIES[key][2], CITIES[key][3]
    return KNOWN_PLACES[key][1], KNOWN_PLACES[key][2]


# (hours relative to NOW, (lat, lon))
ROUTES: dict[str, tuple[str, list[tuple[float, tuple[float, float]]]]] = {
    story.HERO_TRUCK: (story.HERO_SHIPMENT, [
        (-15.5, _p("sofia")), (-13.0, _p("sofia")),          # loading
        (-11.8, _p("kalotina")), (-11.0, _p("kalotina")),    # border BG/RS
        (-9.3, (43.3209, 21.8958)),                          # Niš
        (-6.6, _p("belgrade")), (-5.85, _p("belgrade")),     # 45 min break
        (-3.67, _p("batrovci")), (0.0, (45.0571, 19.0962)),  # stuck in the Batrovci queue (creeping)
    ]),
    "trk_0004": ("shp_0902", [
        (-8.5, _p("sofia")), (-7.3, _p("kalotina")), (-6.8, _p("kalotina")),
        (-2.0, _p("belgrade")), (0.0, (45.2671, 19.8335)),  # near Novi Sad
    ]),
    "trk_0005": ("shp_0903", [
        (-5.5, _p("bucharest")), (-4.0, _p("ruse_bridge")), (-3.5, _p("ruse_bridge")),
        (0.0, (42.9078, 23.7934)),  # Botevgrad
    ]),
}
PARKED = {"trk_0001": "sofia_depot", "trk_0002": "sofia_depot", "trk_0006": "sofia_depot"}


def _bearing(a, b) -> float:
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dl = math.radians(b[1] - a[1])
    x = math.sin(dl) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dl)
    return round((math.degrees(math.atan2(x, y)) + 360) % 360, 1) % 360


def _interp(points, t: datetime):
    for (h0, p0), (h1, p1) in zip(points, points[1:]):
        t0, t1 = NOW + timedelta(hours=h0), NOW + timedelta(hours=h1)
        if t0 <= t <= t1:
            f = (t - t0) / (t1 - t0) if t1 > t0 else 0
            pos = (p0[0] + (p1[0] - p0[0]) * f, p0[1] + (p1[1] - p0[1]) * f)
            hours = (h1 - h0) or 1
            speed = haversine_km(*p0, *p1) / hours
            return pos, speed, _bearing(p0, p1) if p0 != p1 else None
    return None


def generate(rng: random.Random) -> dict[str, list]:
    pings: list[GpsPing] = []
    for truck_id, (shipment_id, points) in ROUTES.items():
        t = NOW + timedelta(hours=points[0][0])
        n = 0
        while t <= NOW:
            hit = _interp(points, t)
            if hit:
                (lat, lon), speed, heading = hit
                moving = speed > 3
                pings.append(GpsPing(
                    id=f"gps_{truck_id[4:]}{n:04d}",
                    truck_id=truck_id,
                    shipment_id=shipment_id,
                    recorded_at=t,
                    lat=round(lat + (rng.uniform(-0.002, 0.002) if moving else 0), 5),
                    lon=round(lon + (rng.uniform(-0.002, 0.002) if moving else 0), 5),
                    speed_kmh=round(max(0.0, speed + rng.uniform(-6, 6)) if moving else rng.choice([0.0, 0.0, 2.0]), 1),
                    heading_deg=heading,
                ))
                n += 1
            t += STEP
    for truck_id, place in PARKED.items():
        lat, lon = _p(place)
        pings.append(GpsPing(id=f"gps_{truck_id[4:]}0000", truck_id=truck_id, recorded_at=NOW - timedelta(minutes=15),
                             lat=lat, lon=lon, speed_kmh=0.0))
    return {"gps_pings": pings}
