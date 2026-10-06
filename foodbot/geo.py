import logging

import httpx

from foodbot import config
from foodbot.services.distance import haversine_km  # noqa: F401  (re-exported for callers)

log = logging.getLogger(__name__)


async def reverse_geocode(lat, lon):
    if not config.GEOAPIFY_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=6) as c:
            r = await c.get(
                "https://api.geoapify.com/v1/geocode/reverse",
                params={"lat": lat, "lon": lon, "format": "json", "apiKey": config.GEOAPIFY_API_KEY},
            )
            r.raise_for_status()
            results = r.json().get("results") or []
            return results[0].get("formatted") if results else None
    except Exception as e:
        log.warning("reverse_geocode failed: %s", type(e).__name__)
        return None
