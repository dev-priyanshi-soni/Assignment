import time
from django.conf import settings
from django.core.cache import cache
import requests

_LAST_REQUEST_AT = 0.0

def geocode_location(query: str) -> dict:
    global _LAST_REQUEST_AT

    cache_key = "geocode:" + query.strip().lower()
    cached = cache.get(cache_key)
    if cached:
        return cached

    # Public Nominatim asks clients to limit usage to <= 1 request/second.
    wait = 1.05 - (time.monotonic() - _LAST_REQUEST_AT)
    if wait > 0:
        time.sleep(wait)

    url = f"{settings.NOMINATIM_BASE_URL.rstrip('/')}/search"
    params = {
        "q": f"{query}, USA",
        "format": "jsonv2",
        "limit": 1,
        "countrycodes": "us",
    }
    headers = {"User-Agent": settings.NOMINATIM_USER_AGENT}

    response = requests.get(url, params=params, headers=headers, timeout=15)
    _LAST_REQUEST_AT = time.monotonic()
    response.raise_for_status()

    results = response.json()
    if not results:
        raise ValueError(f"Could not geocode location: {query}")

    result = results[0]
    data = {
        "input": query,
        "display_name": result.get("display_name"),
        "lat": float(result["lat"]),
        "lon": float(result["lon"]),
    }
    cache.set(cache_key, data, settings.GEOCODE_CACHE_SECONDS)
    return data
