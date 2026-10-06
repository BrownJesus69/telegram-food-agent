from __future__ import annotations

from dataclasses import dataclass
from typing import List
import re
from difflib import SequenceMatcher

from services import catalogue
from services.distance import haversine_km
from services.eta import estimate_eta


GENERIC_ITEM_NAMES = {
    "veg meal",
    "chicken meal",
    "paneer starter",
    "soft drink",
    "dessert cup",
    "cappuccino",
    "cold coffee",
    "brownie",
    "fruit bowl",
    "lime soda",
    "filter coffee",
}

STOPWORDS = {
    "i", "am", "hungry", "want", "need", "would", "like", "to", "eat",
    "give", "me", "show", "find", "near", "nearby", "within", "under",
    "below", "less", "than", "rs", "rupees", "price", "budget", "please",
    "a", "an", "the", "and", "with", "for", "some", "food", "something"
}


@dataclass
class SearchResult:
    item: object
    restaurant: object
    distance_km: float
    eta_min: int
    eta_max: int
    score: float


def _norm(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _tokens(s: str) -> list[str]:
    return [t for t in _norm(s).split() if t and t not in STOPWORDS and not t.isdigit()]


def _meaningful_query_tokens(query_text: str) -> list[str]:
    toks = _tokens(query_text)
    budget_words = {"under", "within", "below", "max"}
    return [t for t in toks if t not in budget_words]


def _is_generic_template_item(item_name: str, item_desc: str = "", category: str = "") -> bool:
    n = _norm(item_name)
    if n in GENERIC_ITEM_NAMES:
        return True

    generic_fragments = [
        "balanced vegetarian meal",
        "complete chicken meal",
        "chef special dessert",
        "chilled beverage",
        "freshly brewed cappuccino",
        "grilled veg sandwich",
        "creamy alfredo pasta",
        "classic chicken shawarma wrap",
        "chargrilled kebab platter",
    ]
    hay = " ".join([_norm(item_name), _norm(item_desc), _norm(category)])
    return any(g in hay for g in generic_fragments)


def _pick(obj, *names, default=None):
    for name in names:
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None and value != "":
                return value
    return default


def _to_float(value, default=None):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _restaurant_lat_lon(rest):
    lat = _pick(
        rest,
        "latitude", "lat", "restaurant_lat", "restaurant_latitude",
        "delivery_lat", "deliverylatitude", "geo_lat"
    )
    lon = _pick(
        rest,
        "longitude", "lon", "lng", "restaurant_lon", "restaurant_longitude",
        "delivery_lon", "deliverylongitude", "geo_lon"
    )

    lat = _to_float(lat)
    lon = _to_float(lon)

    if lat is None or lon is None:
        return None, None

    return lat, lon


def _restaurant_rating(rest) -> float:
    return float(_pick(rest, "rating", "avg_rating", "avgRating", "stars", default=4.0) or 4.0)


def _restaurant_prep_minutes(rest) -> int:
    value = _pick(rest, "prepminutes", "prep_minutes", "prep_time", "preparation_minutes", default=25)
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 25


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _match_score(query_text: str, item) -> float:
    qnorm = _norm(query_text)
    inorm = _norm(getattr(item, "name", ""))
    desc = _norm(getattr(item, "description", ""))
    cat = _norm(getattr(item, "category", ""))

    qtoks = _meaningful_query_tokens(query_text)
    if not qtoks:
        return 0.0

    hay = " ".join([inorm, desc, cat]).strip()
    hay_tokens = set(_tokens(hay))
    overlap_tokens = [t for t in qtoks if t in hay_tokens]
    overlap = len(overlap_tokens)

    phrase_in_name = qnorm in inorm if qnorm else False
    phrase_in_text = qnorm in hay if qnorm else False
    all_tokens_present = all(t in hay_tokens for t in qtoks)
    name_similarity = _similarity(qnorm, inorm)

    if len(qtoks) >= 2:
        if phrase_in_name:
            return 300.0 + (name_similarity * 50.0)

        if all_tokens_present:
            score = 220.0
            if phrase_in_text:
                score += 30.0
            score += overlap * 15.0
            score += name_similarity * 20.0
            return score

        if name_similarity >= 0.86:
            return 180.0 + (name_similarity * 40.0)

        return 0.0

    token = qtoks[0]

    if token == inorm:
        return 220.0
    if token in inorm:
        return 120.0
    if token in desc:
        return 60.0
    if token in cat:
        return 40.0

    if _similarity(token, inorm) >= 0.88:
        return 90.0

    return 0.0


def format_result(r: SearchResult) -> str:
    item = r.item
    rest = r.restaurant
    veg_label = "Veg" if getattr(item, "veg", False) else "Non-veg"
    rating = _restaurant_rating(rest)
    return "\n".join([
        f"{getattr(item, 'name', 'Item')} - {getattr(rest, 'name', 'Restaurant')}",
        f"Price: Rs {int(getattr(item, 'price', 0) or 0)}",
        f"Rating: {rating:.1f}",
        f"Distance: {r.distance_km:.2f} km",
        f"ETA: {r.eta_min}-{r.eta_max} min",
        f"Category: {getattr(item, 'category', 'N/A')}",
        f"Type: {veg_label}",
    ])


def search_items(
    query_text: str,
    user_lat: float,
    user_lon: float,
    budget: int | None = None,
    limit: int = 5,
    max_distance_km: float = 6.0,
    veg_only: bool = False,
) -> List[SearchResult]:
    results: list[SearchResult] = []
    seen_pairs = set()

    qtoks = _meaningful_query_tokens(query_text)
    if not qtoks:
        return []

    for item in catalogue.ITEMS.values():
        rest = catalogue.RESTAURANTS.get(getattr(item, "restaurant_id", None))
        if not rest:
            continue

        if not getattr(item, "active", 1):
            continue
        if not getattr(item, "in_stock", 1):
            continue
        if not getattr(rest, "active", 1):
            continue
        if veg_only and not getattr(item, "veg", False):
            continue

        price = int(getattr(item, "price", 0) or 0)
        if budget is not None and price > budget:
            continue

        if _is_generic_template_item(
            getattr(item, "name", ""),
            getattr(item, "description", ""),
            getattr(item, "category", ""),
        ):
            continue

        score = _match_score(query_text, item)
        if score <= 0:
            continue

        rest_lat, rest_lon = _restaurant_lat_lon(rest)
        if rest_lat is None or rest_lon is None:
            continue

        dist = haversine_km(user_lat, user_lon, rest_lat, rest_lon)
        if dist > max_distance_km:
            continue

        pair_key = (
            _norm(getattr(item, "name", "")),
            _norm(getattr(rest, "name", "")),
            round(dist, 2),
        )
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        eta_min, eta_max = estimate_eta(
            distance_km=dist,
            prep_minutes=_restaurant_prep_minutes(rest),
        )

        rating = _restaurant_rating(rest)
        final_score = score + (rating * 3.0) - (dist * 2.5)

        results.append(
            SearchResult(
                item=item,
                restaurant=rest,
                distance_km=dist,
                eta_min=eta_min,
                eta_max=eta_max,
                score=final_score,
            )
        )

    results.sort(
        key=lambda r: (-r.score, r.distance_km, int(getattr(r.item, "price", 0) or 0))
    )
    return results[:limit]
