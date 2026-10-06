from rapidfuzz import fuzz
from services import catalogue
import config
import geo


def eta_range(rest, dist_km):
    travel = max(10, round(dist_km * rest.min_per_km))
    return rest.prep_min + travel, rest.prep_max + travel + 10


def search(q, lat, lon, limit=3):
    out = []
    for it in catalogue.ITEMS.values():
        if not it.available:
            continue
        rest = catalogue.RESTAURANTS[it.restaurant_id]
        if not rest.is_open:
            continue
        if q.budget and it.price > q.budget:
            continue
        if q.diet == "veg" and not it.veg:
            continue
        if q.diet == "non_veg" and it.veg:
            continue
        dist = geo.haversine_km(lat, lon, rest.lat, rest.lon)
        if dist > rest.radius_km:
            continue
        terms = [it.name.lower(), *it.aliases]
        match = max(fuzz.WRatio(q.dish, t) for t in terms)
        if match < config.MIN_MATCH:
            continue
        dist_score = max(0.0, 1 - dist / rest.radius_km)
        score = 0.6 * (match / 100) + 0.2 * (rest.rating / 5) + 0.2 * dist_score
        lo, hi = eta_range(rest, dist)
        out.append({"item": it, "rest": rest, "dist": dist, "match": match,
                    "score": score, "eta": (lo, hi)})
    out.sort(key=lambda r: (-r["score"], r["dist"]))
    return out[:limit]
