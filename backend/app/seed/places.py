"""Cities (names in original script) and route helpers."""

import math

from app.schemas import Location

CITIES: dict[str, tuple[str, str, float, float]] = {
    # key: (local name, ISO country, lat, lon)
    "sofia": ("София", "BG", 42.6977, 23.3219),
    "pernik": ("Перник", "BG", 42.6052, 23.0378),
    "plovdiv": ("Пловдив", "BG", 42.1354, 24.7453),
    "stara_zagora": ("Стара Загора", "BG", 42.4258, 25.6345),
    "ruse": ("Русе", "BG", 43.8356, 25.9657),
    "varna": ("Варна", "BG", 43.2141, 27.9147),
    "munich": ("München", "DE", 48.1351, 11.5820),
    "vienna": ("Wien", "AT", 48.2082, 16.3738),
    "bucharest": ("București", "RO", 44.4268, 26.1025),
    "constanta": ("Constanța", "RO", 44.1598, 28.6348),
    "bursa": ("Bursa", "TR", 40.1885, 29.0610),
    "istanbul": ("İstanbul", "TR", 41.0082, 28.9784),
    "skopje": ("Скопје", "MK", 41.9981, 21.4254),
    "thessaloniki": ("Θεσσαλονίκη", "GR", 40.6401, 22.9444),
    "milan": ("Milano", "IT", 45.4642, 9.1900),
    "belgrade": ("Београд", "RS", 44.7866, 20.4489),
}

# Known places for GPS context (border crossings are where most delays happen).
# TODO(owner B): use these to explain delays ("stationary at Batrovci border for 3h40m").
KNOWN_PLACES: dict[str, tuple[str, float, float]] = {
    "kalotina": ("Калотина (BG/RS border)", 42.9896, 22.8711),
    "batrovci": ("Batrovci (RS/HR border)", 45.0567, 19.1003),
    "ruse_bridge": ("Дунав мост Русе–Гюргево (BG/RO border)", 43.8869, 25.9536),
    "kapitan_andreevo": ("Капитан Андреево (BG/TR border)", 41.7183, 26.3253),
    "kulata": ("Кулата (BG/GR border)", 41.3897, 23.3667),
    "sofia_depot": ("Склад Казичене", 42.6650, 23.4610),
}


def loc(key: str) -> Location:
    name, country, lat, lon = CITIES[key]
    return Location(city=name, country=country, lat=lat, lon=lon)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def road_km(a: str, b: str) -> int:
    """Rough road distance: great-circle x 1.25."""
    _, _, la, lo = CITIES[a]
    _, _, lb, lob = CITIES[b]
    return int(haversine_km(la, lo, lb, lob) * 1.25)
