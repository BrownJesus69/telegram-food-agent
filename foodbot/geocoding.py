"""Turn what a customer types ("Embassy Tech Village, Bellandur", "near Indiranagar metro") into coordinates.

Two sources, both free: Geoapify forward geocoding (when a key is configured) restricted to Bengaluru, and a
built-in neighbourhood table derived from the catalogue so the bot still works with no network or key.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import httpx
from rapidfuzz import fuzz

from foodbot import config
from foodbot.services import catalogue

log = logging.getLogger(__name__)

BENGALURU_BBOX = (12.80, 13.16, 77.45, 77.80)      # lat_min, lat_max, lon_min, lon_max
CITY_CENTRE = (12.9716, 77.5946)


@dataclass(frozen=True)
class Place:
    label: str
    lat: float
    lon: float
    precision: str = "exact"          # "exact" (street/building) or "area" (neighbourhood centre)


def in_bengaluru(lat: float, lon: float) -> bool:
    return BENGALURU_BBOX[0] <= lat <= BENGALURU_BBOX[1] and BENGALURU_BBOX[2] <= lon <= BENGALURU_BBOX[3]


def popular_areas(n: int = 8) -> list[str]:
    locs = catalogue.localities()
    return [name for name, _ in sorted(((k, v[2]) for k, v in locs.items()), key=lambda kv: (-kv[1], kv[0]))[:n]]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", (s or "").lower())).strip()


def area_matches(text: str, limit: int = 3) -> list[Place]:
    """Neighbourhoods named in (or fuzzily close to) the text."""
    q = _norm(text)
    if not q:
        return []
    scored = []
    for name, (lat, lon, _) in catalogue.localities().items():
        n = _norm(name)
        if re.search(rf"\b{re.escape(n)}\b", q):
            score = 100.0
        else:
            score = fuzz.WRatio(q, n) if len(q) >= 4 else 0
        if score >= 88:
            scored.append((-score, name, lat, lon))
    scored.sort()
    return [Place(f"{name} (area centre)", lat, lon, "area") for _, name, lat, lon in scored[:limit]]


async def geoapify_search(text: str, limit: int = 3) -> list[Place]:
    if not config.GEOAPIFY_API_KEY:
        return []
    lat0, lon0 = CITY_CENTRE
    try:
        async with httpx.AsyncClient(timeout=6) as c:
            r = await c.get(
                "https://api.geoapify.com/v1/geocode/search",
                params={
                    "text": f"{text}, Bengaluru",
                    "filter": f"rect:{BENGALURU_BBOX[2]},{BENGALURU_BBOX[0]},{BENGALURU_BBOX[3]},{BENGALURU_BBOX[1]}",
                    "bias": f"proximity:{lon0},{lat0}",
                    "limit": limit,
                    "format": "json",
                    "apiKey": config.GEOAPIFY_API_KEY,
                },
            )
            r.raise_for_status()
            out = []
            for res in r.json().get("results") or []:
                lat, lon = res.get("lat"), res.get("lon")
                if lat is None or lon is None or not in_bengaluru(lat, lon):
                    continue
                out.append(Place(res.get("formatted") or text, float(lat), float(lon), "exact"))
            return out
    except Exception as e:
        log.warning("geoapify_search failed: %s", type(e).__name__)
        return []


async def search_address(text: str) -> list[Place]:
    """Best-first candidates for a typed address; never returns anything outside Bengaluru."""
    text = (text or "").strip()[:200]
    if len(text) < 3:
        return []
    found = await geoapify_search(text)
    seen = {(round(p.lat, 3), round(p.lon, 3)) for p in found}
    for p in area_matches(text):
        if (round(p.lat, 3), round(p.lon, 3)) not in seen:
            found.append(p)
    return found[:4]


# ----------------------------------------------------------------- input validation
_PHONE = re.compile(r"^(?:\+?91[\s-]?)?([6-9]\d{4}[\s-]?\d{5})$")


def normalise_phone(text: str) -> str | None:
    """Indian mobile number -> '+91XXXXXXXXXX', or None if it isn't one."""
    m = _PHONE.match((text or "").strip())
    return "+91" + re.sub(r"[\s-]", "", m.group(1)) if m else None


def clean_name(text: str) -> str | None:
    name = re.sub(r"\s+", " ", re.sub(r"[^\w\s.'-]", "", text or "", flags=re.UNICODE)).strip()
    return name[:40] if len(name) >= 2 else None
