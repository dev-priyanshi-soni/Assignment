from functools import lru_cache
import json
import math
from pathlib import Path

from django.conf import settings
from shapely.geometry import LineString, Point

EARTH_RADIUS_M = 6_371_000.0
METERS_PER_MILE = 1609.344

def _project(lon, lat, lon0, lat0):
    """Local equirectangular projection. Good enough for a route corridor."""
    x = math.radians(lon - lon0) * EARTH_RADIUS_M * math.cos(math.radians(lat0))
    y = math.radians(lat - lat0) * EARTH_RADIUS_M
    return x, y

def _route_projection(route_coords):
    lons = [p[0] for p in route_coords]
    lats = [p[1] for p in route_coords]
    lon0 = sum(lons) / len(lons)
    lat0 = sum(lats) / len(lats)

    projected = [_project(lon, lat, lon0, lat0) for lon, lat in route_coords]
    return LineString(projected), lon0, lat0

@lru_cache(maxsize=1)
def load_stations():
    path = Path(settings.BASE_DIR) / "data" / "geocoded_stations.json"
    if not path.exists():
        raise ValueError(
            "data/geocoded_stations.json is missing. "
            "Run scripts/preprocess_stations.py first."
        )
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def find_route_stations(route_coords, route_distance_miles, corridor_miles=25):
    stations = load_stations()
    route_line, lon0, lat0 = _route_projection(route_coords)

    corridor_m = corridor_miles * METERS_PER_MILE
    candidates = []

    for station in stations:
        try:
            point = Point(_project(
                float(station["longitude"]),
                float(station["latitude"]),
                lon0,
                lat0,
            ))
            distance_to_route = route_line.distance(point)
            if distance_to_route > corridor_m:
                continue

            # Shapely project returns meters along the projected route.
            position_m = route_line.project(point)
            position_miles = position_m / METERS_PER_MILE

            if position_miles <= 0 or position_miles >= route_distance_miles:
                continue

            candidates.append({
                **station,
                "route_position_miles": round(position_miles, 2),
                "distance_from_route_miles": round(
                    distance_to_route / METERS_PER_MILE, 2
                ),
            })
        except (KeyError, TypeError, ValueError):
            continue

    # Deduplicate same physical stop/name/position and retain cheapest price.
    candidates.sort(key=lambda x: (x["route_position_miles"], x["price"]))
    deduped = []
    seen = set()
    for s in candidates:
        key = (
            s.get("truckstop_id"),
            s.get("name"),
            round(s["route_position_miles"], 1),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(s)

    return deduped
