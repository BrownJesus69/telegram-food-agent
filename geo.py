import logging
from math import asin, cos, radians, sin, sqrt

import httpx

import config

log = logging.getLogger(__name__)


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = radians(lat1), radians(lat2)
    dp, dl = p2 - p1, radians(lon2 - lon1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * 6371.0088 * asin(sqrt(a))


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


async def nearby_restaurants(lat, lon, radius_m=3000, limit=5):
    if not config.GEOAPIFY_API_KEY:
        return []
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(
                "https://api.geoapify.com/v2/places",
                params={
                    "categories": "catering.restaurant,catering.fast_food",
                    "filter": f"circle:{lon},{lat},{radius_m}",
                    "bias": f"proximity:{lon},{lat}",
                    "limit": limit,
                    "apiKey": config.GEOAPIFY_API_KEY,
                },
            )
            r.raise_for_status()
            out = []
            for f in r.json().get("features", []):
                p = f.get("properties", {})
                if p.get("name"):
                    out.append({
                        "name": p["name"],
                        "address": p.get("address_line2") or p.get("formatted") or "",
                        "distance_m": p.get("distance"),
                    })
            return out
    except Exception as e:
        log.warning("nearby_restaurants failed: %s", type(e).__name__)
        return []
