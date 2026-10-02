from django.conf import settings
from django.core.cache import cache
import requests

def get_route(start_lon, start_lat, finish_lon, finish_lat):
    cache_key = (
        f"route:{round(start_lat,5)}:{round(start_lon,5)}:"
        f"{round(finish_lat,5)}:{round(finish_lon,5)}"
    )
    cached = cache.get(cache_key)
    if cached:
        return cached

    coordinates = f"{start_lon},{start_lat};{finish_lon},{finish_lat}"
    url = f"{settings.OSRM_BASE_URL.rstrip('/')}/route/v1/driving/{coordinates}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
        "alternatives": "false",
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()

    if payload.get("code") != "Ok" or not payload.get("routes"):
        raise ValueError("No driving route was found for the supplied locations.")

    route = payload["routes"][0]
    data = {
        "distance_miles": round(route["distance"] / 1609.344, 2),
        "duration_minutes": round(route["duration"] / 60, 1),
        "geometry": route["geometry"],
    }

    cache.set(cache_key, data, settings.ROUTE_CACHE_SECONDS)
    return data
