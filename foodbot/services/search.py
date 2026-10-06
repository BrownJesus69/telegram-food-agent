"""Catalogue search: fuzzy dish matching + hard filters + a transparent ranking formula.

Hard filters (never relaxed silently): restaurant active and open now, item in stock, within the
restaurant's own delivery radius, budget, diet. Ranking blends relevance, rating, proximity,
popularity and (optionally) fit to the current meal slot.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache

from rapidfuzz import fuzz

from foodbot import config
from foodbot.services import catalogue
from foodbot.services.distance import haversine_km
from foodbot.services.eta import estimate_eta

STOPWORDS = {
    "i", "am", "hungry", "want", "need", "would", "like", "to", "eat", "give", "me", "show", "find", "near",
    "nearby", "within", "under", "below", "less", "than", "rs", "rupees", "price", "budget", "please", "a", "an",
    "the", "and", "with", "for", "some", "food", "something", "order", "get", "craving", "any", "good", "best",
    "in", "at", "of", "from", "on", "my", "us", "we", "can", "could", "you", "can't", "have", "now", "today",
}


@dataclass
class SearchResult:
    item: catalogue.Item
    restaurant: catalogue.Restaurant
    distance_km: float
    eta_min: int
    eta_max: int
    score: float
    match: float = 0.0


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", (s or "").lower())).strip()


def query_tokens(text: str) -> list[str]:
    return [t for t in _norm(text).split() if t not in STOPWORDS and not t.isdigit()]


def _token_score(token: str, name_tokens: set[str], desc_tokens: set[str]) -> float:
    """How well one query word is explained by a dish: exact name word 100, typo of a name word 88, only in the description 66."""
    if token in name_tokens:
        return 100.0
    if len(token) >= 4 and any(len(h) >= 4 and fuzz.ratio(token, h) >= 85 for h in name_tokens):
        return 88.0
    if token in desc_tokens:
        return 66.0
    if len(token) >= 5 and any(len(h) >= 5 and fuzz.ratio(token, h) >= 88 for h in desc_tokens):
        return 60.0
    return 0.0


@lru_cache(maxsize=8192)
def _relevance(query: str, name: str, aliases: tuple[str, ...], description: str, category: str) -> float:
    """0-100 relevance of a dish to the query; cached because many restaurants share a dish.

    Every meaningful query word must be explained by the dish (name/aliases score highest, description lowest);
    the result is the average, so one shared word can never carry a multi-word query. Whole-name matches get a bonus.
    """
    q = _norm(query)
    toks = query_tokens(query)
    if not q or not toks:
        return 0.0
    terms = [_norm(t) for t in aliases] or [_norm(name)]
    if q in terms:
        return 100.0
    name_tokens = set(_norm(" ".join([name, *aliases])).split())
    desc_tokens = set(_norm(" ".join([description, category])).split())
    scores = [_token_score(t, name_tokens, desc_tokens) for t in toks]
    covered = sum(sc >= 60 for sc in scores) / len(toks)
    if covered < 0.66 or min(scores) == 0 and len(toks) <= 2:
        return min(sum(scores) / len(scores), 60.0)
    score = sum(scores) / len(scores)
    if any(q in t or t in q for t in terms if len(t) >= 4):
        score = max(score, 95.0)                      # the query is (part of) a whole alias, e.g. "masala dosa" in "mysore masala dosa"
    return score


def _diet_ok(item: catalogue.Item, diet: str | None) -> bool:
    if not diet:
        return True
    if diet == "veg":
        return item.diet == "veg"
    if diet in ("non_veg", "nonveg"):
        return item.diet in ("nonveg", "egg")
    if diet == "egg":
        return item.diet == "egg"
    return True


def search_items(
    query_text: str,
    user_lat: float,
    user_lon: float,
    budget: int | None = None,
    limit: int = 5,
    diet: str | None = None,
    slot: str | None = None,
    now: datetime | None = None,
    include_closed: bool = False,
    max_distance_km: float | None = None,
    one_per_restaurant: bool = True,
) -> list[SearchResult]:
    if not query_tokens(query_text):
        return []
    best_by_rest: dict[str, SearchResult] = {}
    results: list[SearchResult] = []

    for item in catalogue.ITEMS.values():
        if not item.available:
            continue
        if budget is not None and item.price > budget:
            continue
        if not _diet_ok(item, diet):
            continue
        match = _relevance(query_text, item.name, item.aliases, item.description, item.category)
        if match < config.MIN_MATCH:
            continue
        rest = catalogue.RESTAURANTS.get(item.restaurant_id)
        if rest is None or not rest.active:
            continue
        if not include_closed and not rest.open_at(now):
            continue
        dist = haversine_km(user_lat, user_lon, rest.lat, rest.lon)
        if dist > (max_distance_km if max_distance_km is not None else rest.radius_km):
            continue

        prox = max(0.0, 1.0 - dist / max(rest.radius_km, 0.1))
        rating = min(max((rest.rating - 3.0) / 2.0, 0.0), 1.0)
        popular = 1.0 if ("bestseller" in item.tags or "must-try" in item.tags) else 0.0
        slot_fit = 1.0 if (slot and slot in item.slots) else 0.0
        score = 0.55 * (match / 100) + 0.15 * rating + 0.15 * prox + 0.08 * popular + 0.07 * slot_fit

        lo, hi = estimate_eta(dist, rest.prep_min, now)
        res = SearchResult(item, rest, dist, lo, hi, score, match)
        if one_per_restaurant:
            cur = best_by_rest.get(rest.id)
            if cur is None or (res.score, -res.item.price) > (cur.score, -cur.item.price):
                best_by_rest[rest.id] = res
        else:
            results.append(res)

    pool = list(best_by_rest.values()) if one_per_restaurant else results
    pool.sort(key=lambda r: (-r.score, r.distance_km, r.item.price))
    return pool[:limit]


def closed_matches(query_text: str, user_lat: float, user_lon: float, budget: int | None = None,
                   diet: str | None = None, now: datetime | None = None, limit: int = 3) -> list[SearchResult]:
    """Dishes that match and are in range but whose restaurant is closed right now (for helpful messaging)."""
    open_ids = {r.restaurant.id for r in search_items(query_text, user_lat, user_lon, budget, 10_000, diet, now=now)}
    out = [r for r in search_items(query_text, user_lat, user_lon, budget, 10_000, diet, now=now, include_closed=True)
           if r.restaurant.id not in open_ids]
    return out[:limit]


def format_result(r: SearchResult) -> str:
    item, rest = r.item, r.restaurant
    return "\n".join([
        f"{item.name} - {rest.name}",
        f"Price: Rs {item.price}",
        f"Rating: {rest.rating:.1f}",
        f"Distance: {r.distance_km:.2f} km",
        f"ETA: {r.eta_min}-{r.eta_max} min",
        f"Category: {item.category}",
        f"Type: {'Veg' if item.veg else 'Non-veg'}",
    ])


def relevance(dish: str, item: catalogue.Item) -> float:
    """0-100 relevance of one catalogue item to a dish phrase (public wrapper over the cached scorer)."""
    return _relevance(dish, item.name, item.aliases, item.description, item.category)
