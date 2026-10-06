"""Turn a FoodRequest into grounded recommendations.

Everything here reads the catalogue; nothing is generated. Hard constraints (open now, in stock, delivery
radius, diet, budget, allergens) are never relaxed. Each recommendation carries human-readable `reasons`
computed from catalogue fields, so every claim shown to the customer is checkable.
"""
from __future__ import annotations

import math
import re
from copy import copy
from dataclasses import dataclass, field
from datetime import datetime

from foodbot import config
from foodbot.concierge.intent import FoodRequest
from foodbot.services import catalogue
from foodbot.services.distance import haversine_km
from foodbot.services.eta import estimate_eta
from foodbot.services.search import relevance

MAX_PER_LINE = 10          # cart limit per item
# menu sections that are drinks / sweets: never suggested as a "meal" when the customer named no dish
DRINK_SECTIONS = {"Beverages", "Coffee & Beverages", "Juices & Shakes"}
SWEET_SECTIONS = {"Sweets & Savouries", "Bakery", "Desserts & Ice Cream"}
_HOT_DRINK = ("chai", "tea", "coffee", "kaapi", "kahwa")
NON_MAIN = DRINK_SECTIONS | SWEET_SECTIONS | {"Sandwiches"}


@dataclass
class Line:
    item: catalogue.Item
    qty: int

    @property
    def amount(self) -> int:
        return self.item.price * self.qty


@dataclass
class Recommendation:
    restaurant: catalogue.Restaurant
    lines: list[Line]
    distance_km: float
    eta_min: int
    eta_max: int
    score: float
    reasons: list[str] = field(default_factory=list)

    @property
    def item(self) -> catalogue.Item:
        return self.lines[0].item

    @property
    def subtotal(self) -> int:
        return sum(ln.amount for ln in self.lines)

    @property
    def total(self) -> int:
        return self.subtotal + self.restaurant.delivery_fee

    @property
    def is_bundle(self) -> bool:
        return len(self.lines) > 1 or self.lines[0].qty > 1


_SERVES = re.compile(r"serves?\s+(\d+)", re.I)


def serves(item: catalogue.Item) -> int:
    m = _SERVES.search(item.name)
    return int(m.group(1)) if m else 1


# ----------------------------------------------------------------------------- hard filters
def _spice_ok(item: catalogue.Item, spice: str | None) -> bool:
    if not spice:
        return True
    return {"mild": item.spice <= 1, "medium": 1 <= item.spice <= 2, "hot": item.spice >= 2}[spice]


def _exclusions_ok(item: catalogue.Item, exclude: list[str]) -> bool:
    for ex in exclude:
        if ex == "onion-garlic":
            if "jain" not in item.tags:
                return False
        elif ex in item.allergens:
            return False
    return True


_CUISINE_KEYS = {
    "coastal": ("coastal", "mangalorean", "seafood"), "street food": ("chaat", "street"), "cafe": ("cafe", "coffee"),
    "dessert": ("dessert", "ice cream", "sweet"), "healthy": ("healthy", "salad", "bowl"), "hyderabadi": ("hyderabadi", "biryani"),
    "asian": ("asian", "thai", "japanese", "korean", "tibetan", "momo"), "bakery": ("bakery", "cake"),
    "pizza": ("pizza",), "burger": ("burger",), "biryani": ("biryani",),
}


def _cuisine_ok(rest: catalogue.Restaurant, cuisine: str | None) -> bool:
    if not cuisine:
        return True
    hay = f"{rest.cuisine} {rest.category} {' '.join(rest.tags)}".lower()
    return any(k in hay for k in _CUISINE_KEYS.get(cuisine, (cuisine,)))


def _is_drink(item: catalogue.Item) -> bool:
    if item.category in DRINK_SECTIONS:
        return True
    return item.category == "Chai & Snacks" and any(w in item.name.lower().split() for w in _HOT_DRINK)


def _unwanted_kind(req: FoodRequest, item: catalogue.Item, hard_slot: str | None) -> bool:
    """With no dish named, don't answer 'I'm hungry' / 'light dinner' with a cup of tea or a pastry."""
    if req.dishes or "sweet" in req.tags:
        return False
    if _is_drink(item) and hard_slot != "snack":
        return True
    return item.category in SWEET_SECTIONS and hard_slot in ("lunch", "dinner", "breakfast")


def _hard_slot(req: FoodRequest, current_slot: str | None) -> str | None:
    """Which meal slot a dish must belong to. A named dish is never slot-filtered."""
    if req.dishes:
        return None
    if req.slot:
        return req.slot
    if not (req.tags or req.cuisine):
        return current_slot            # "I'm hungry": suggest what suits this time of day
    return None


def _candidates(req: FoodRequest, lat: float, lon: float, now: datetime | None, hard_slot: str | None,
                *, check_open: bool = True, check_radius: bool = True, kind_filter: bool = True):
    """Yield (item, restaurant, distance_km, relevance 0-100) for everything that passes every hard constraint.

    `check_open` / `check_radius` exist only so `diagnose` can ask "would this match if the kitchen were open?".
    """
    for item in catalogue.ITEMS.values():
        if not item.available or (req.diet and item.diet != req.diet) or not _spice_ok(item, req.spice):
            continue
        if not _exclusions_ok(item, req.exclude):
            continue
        rest = catalogue.RESTAURANTS.get(item.restaurant_id)
        if rest is None or not rest.active or (check_open and not rest.open_at(now)) or not _cuisine_ok(rest, req.cuisine):
            continue
        dist = haversine_km(lat, lon, rest.lat, rest.lon)
        if check_radius and dist > rest.radius_km:
            continue
        if req.dishes:
            rel = max(relevance(d, item) for d in req.dishes)
            if rel < config.MIN_MATCH:
                continue
        else:
            rel = 55.0
            if req.tags and not any(t in item.tags for t in req.tags):
                continue                                    # "something sweet" must actually be tagged sweet
            if hard_slot and hard_slot not in item.slots:
                continue
            if kind_filter and _unwanted_kind(req, item, hard_slot):
                continue
        yield item, rest, dist, rel


# ----------------------------------------------------------------------------- scoring
def _reasons(req: FoodRequest, item: catalogue.Item, rest: catalogue.Restaurant, dist: float, slot: str | None) -> list[str]:
    out = []
    if "bestseller" in item.tags:
        out.append("bestseller")
    elif "must-try" in item.tags:
        out.append("must-try")
    if slot and slot in item.slots and not req.dishes and (req.slot or not req.has_target):
        out.append(f"{'late-night' if slot == 'latenight' else slot} favourite")
    if "onion-garlic" in req.exclude and "jain" in item.tags:
        out.append("Jain-friendly (no onion/garlic)")
    out += [f"no {ex}" for ex in req.exclude if ex != "onion-garlic"]
    out += [t for t in req.tags if t in item.tags]
    if req.spice and item.spice:
        out.append("🌶" * item.spice + " spice")
    if rest.rating >= 4.4:
        out.append(f"{rest.rating:.1f}★ kitchen")
    if dist <= 1.5:
        out.append("very close")
    if item.calories and ({"light", "healthy"} & set(req.tags)):
        out.append(f"{item.calories} kcal")
    return list(dict.fromkeys(out))[:4]


def _score(req: FoodRequest, item, rest, dist, rel, slot, eta_hi) -> float:
    prox = max(0.0, 1.0 - dist / max(rest.radius_km, 0.1))
    rating = min(max((rest.rating - 3.0) / 2.0, 0.0), 1.0)
    popular = 1.0 if ("bestseller" in item.tags or "must-try" in item.tags) else 0.0
    slot_fit = 1.0 if (slot and slot in item.slots) else 0.0
    tag_fit = (sum(t in item.tags for t in req.tags) / len(req.tags)) if req.tags else 0.0
    price_fit = 0.0
    if req.budget:
        unit_budget = req.budget / req.servings if req.budget_scope == "total" else req.budget
        price_fit = max(0.0, 1.0 - item.price / max(unit_budget, 1))
    return (0.40 * rel / 100 + 0.14 * rating + 0.12 * prox + 0.08 * popular + 0.06 * slot_fit + 0.08 * tag_fit
            + 0.07 * price_fit + 0.05 * max(0.0, 1.0 - eta_hi / 90))


def _sort_key(req: FoodRequest, rec: Recommendation):
    return {
        "cheapest": (rec.subtotal, -rec.score),
        "fastest": (rec.eta_max, -rec.score),
        "top_rated": (-rec.restaurant.rating, -rec.score),
        "nearest": (rec.distance_km, -rec.score),
    }.get(req.sort, (-rec.score, rec.distance_km))


def _budget_ok(req: FoodRequest, lines: list[Line], people: int) -> bool:
    """item: every unit price fits; per_person: basket / people fits; total: whole basket fits."""
    if not req.budget:
        return True
    subtotal = sum(ln.amount for ln in lines)
    if req.budget_scope == "item":
        return all(ln.item.price <= req.budget for ln in lines)
    if req.budget_scope == "per_person":
        return subtotal <= req.budget * max(people, 1)
    return subtotal <= req.budget


def _qty_for(item: catalogue.Item, people: int, requested: int) -> int:
    if people > 1:
        return max(1, min(MAX_PER_LINE, math.ceil(people / serves(item))))
    return max(1, min(MAX_PER_LINE, requested))


# ----------------------------------------------------------------------------- planning
def recommend(req: FoodRequest, lat: float, lon: float, now: datetime | None = None, limit: int = 5,
              current_slot: str | None = None) -> list[Recommendation]:
    """Best options for the request, one kitchen each, diversified by dish. Groups and bundles are planned here too."""
    recs = _recommend(req, lat, lon, now, limit, current_slot)
    for rec in recs:                                     # a kitchen's minimum order is shown, not hidden: the cart enforces it
        if rec.subtotal < rec.restaurant.min_order:
            rec.reasons.insert(0, f"min order ₹{rec.restaurant.min_order}")
    return recs


def _recommend(req: FoodRequest, lat: float, lon: float, now: datetime | None, limit: int, current_slot: str | None) -> list[Recommendation]:
    req.clean()
    if req.groups:
        return _plan_groups(req, lat, lon, now, limit, current_slot)
    if req.combine and len(req.dishes) >= 2:
        bundles = _plan_bundles(req, lat, lon, now, limit, current_slot)
        if bundles:
            return bundles
        # no single kitchen has every dish: fall through and treat the dishes as alternatives

    slot = req.slot or current_slot
    per_rest: dict[str, Recommendation] = {}
    for item, rest, dist, rel in _candidates(req, lat, lon, now, _hard_slot(req, current_slot)):
        line = Line(item, _qty_for(item, req.servings, req.quantity))
        if not _budget_ok(req, [line], req.servings) or line.amount < 0:
            continue
        lo, hi = estimate_eta(dist, rest.prep_min, now)
        rec = Recommendation(rest, [line], dist, lo, hi, _score(req, item, rest, dist, rel, slot, hi),
                             _reasons(req, item, rest, dist, slot))
        cur = per_rest.get(rest.id)
        if cur is None or (rec.score, -rec.item.price) > (cur.score, -cur.item.price):
            per_rest[rest.id] = rec
    return _diversify(sorted(per_rest.values(), key=lambda r: _sort_key(req, r)), limit)


def _diversify(ranked: list[Recommendation], limit: int) -> list[Recommendation]:
    """Prefer different dishes before repeating one (so 'something sweet' isn't five identical gulab jamuns)."""
    picked, seen, repeats = [], set(), []
    for rec in ranked:
        if rec.item.name in seen:
            repeats.append(rec)
        else:
            seen.add(rec.item.name)
            picked.append(rec)
        if len(picked) == limit:
            return picked
    return (picked + repeats)[:limit]


def _unfiltered(req: FoodRequest) -> FoodRequest:
    """Same hard constraints, but no dish/tag/slot targeting: enumerates every orderable item."""
    clone = copy(req)
    clone.dishes, clone.tags, clone.slot, clone.groups, clone.combine = [], [], None, [], False
    return clone


def _plan_bundles(req: FoodRequest, lat, lon, now, limit, current_slot) -> list[Recommendation]:
    """Kitchens that can serve every requested dish in one order (e.g. masala dosa + filter coffee)."""
    best: dict[str, dict[str, tuple[catalogue.Item, float]]] = {}
    where: dict[str, tuple[catalogue.Restaurant, float]] = {}
    for item, rest, dist, _ in _candidates(_unfiltered(req), lat, lon, now, None, kind_filter=False):
        for d in req.dishes:
            rel = relevance(d, item)
            if rel >= config.MIN_MATCH:
                found = best.setdefault(rest.id, {})
                if d not in found or (rel, -item.price) > (found[d][1], -found[d][0].price):
                    found[d] = (item, rel)
                where[rest.id] = (rest, dist)
    slot = req.slot or current_slot
    out = []
    for rid, found in best.items():
        if len(found) < len(req.dishes):
            continue
        rest, dist = where[rid]
        lines = [Line(found[d][0], 1) for d in req.dishes]
        if not _budget_ok(req, lines, 1):
            continue
        lo, hi = estimate_eta(dist, rest.prep_min, now)
        rel = sum(found[d][1] for d in req.dishes) / len(req.dishes)
        reasons = ["everything from one kitchen"] + _reasons(req, lines[0].item, rest, dist, slot)[:2]
        out.append(Recommendation(rest, lines, dist, lo, hi, _score(req, lines[0].item, rest, dist, rel, slot, hi), reasons))
    out.sort(key=lambda r: _sort_key(req, r))
    return out[:limit]


def _plan_groups(req: FoodRequest, lat, lon, now, limit, current_slot) -> list[Recommendation]:
    """Mixed-diet group ("2 veg + 2 non-veg"): one kitchen that can feed every group, sized by head-count."""
    per_group: list[dict[str, tuple]] = []
    for g in req.groups:
        sub = copy(req)
        sub.diet, sub.groups, sub.servings, sub.budget, sub.combine = g.diet, [], g.count, None, False
        found: dict[str, tuple] = {}
        for item, rest, dist, rel in _candidates(sub, lat, lon, now, _hard_slot(sub, current_slot)):
            if not req.dishes and (item.category in NON_MAIN or _is_drink(item)):
                continue
            sc = _score(sub, item, rest, dist, rel, req.slot or current_slot, 60)
            if rest.id not in found or sc > found[rest.id][3]:
                found[rest.id] = (item, rest, dist, sc, g.count)
        per_group.append(found)
    common = set(per_group[0]).intersection(*[set(f) for f in per_group[1:]]) if per_group else set()
    out = []
    for rid in common:
        lines, score_sum, rest, dist = [], 0.0, None, 0.0
        for found in per_group:
            item, rest, dist, sc, count = found[rid]
            lines.append(Line(item, _qty_for(item, count, 1)))
            score_sum += sc
        if not _budget_ok(req, lines, req.servings):
            continue
        lo, hi = estimate_eta(dist, rest.prep_min, now)
        reasons = ["serves every diet in one order"] + ([f"{rest.rating:.1f}★ kitchen"] if rest.rating >= 4.3 else [])
        out.append(Recommendation(rest, lines, dist, lo, hi, score_sum / len(per_group), reasons))
    out.sort(key=lambda r: _sort_key(req, r))
    return out[:limit]


# ----------------------------------------------------------------------------- explaining empty results
def diagnose(req: FoodRequest, lat: float, lon: float, now: datetime | None = None, current_slot: str | None = None) -> list[str]:
    """Why did nothing match? Relax one constraint at a time and report which one is the blocker (max 3 hints)."""
    hints: list[str] = []
    hard = _hard_slot(req, current_slot)

    def first_match(r: FoodRequest, **flags):
        for item, rest, dist, _ in _candidates(r, lat, lon, now, hard if r is req else _hard_slot(r, current_slot), **flags):
            line = Line(item, _qty_for(item, r.servings, r.quantity))
            if _budget_ok(r, [line], r.servings):
                return item, rest, dist
        return None

    hit = first_match(req, check_open=False)
    if hit:
        item, rest, _ = hit
        hints.append(f"{item.name} at {rest.name} matches but the kitchen is closed right now (open {rest.hours_label}).")
    hit = first_match(req, check_radius=False)
    if hit:
        item, rest, dist = hit
        hints.append(f"{item.name} at {rest.name} matches but is {dist:.1f} km away, beyond its {rest.radius_km:g} km delivery range. "
                     "Try another delivery address.")
    relaxations = [
        ("budget", req.budget, lambda r: setattr(r, "budget", None)),
        ("diet", req.diet, lambda r: setattr(r, "diet", None)),
        ("exclusions", req.exclude, lambda r: setattr(r, "exclude", [])),
        ("spice", req.spice, lambda r: setattr(r, "spice", None)),
        ("meal-time", req.slot, lambda r: setattr(r, "slot", None)),
        ("cuisine", req.cuisine, lambda r: setattr(r, "cuisine", None)),
        ("tags", req.tags, lambda r: setattr(r, "tags", [])),
    ]
    for name, current, relax in relaxations:
        if not current or len(hints) >= 3:
            continue
        probe = copy(req)
        relax(probe)
        if name == "budget":
            probe.sort = "cheapest"                     # so "cheapest match" really is the cheapest one
        recs = recommend(probe, lat, lon, now, limit=1, current_slot=current_slot)
        if not recs:
            continue
        rec = recs[0]
        if name == "budget":
            hints.append(f"Cheapest match is ₹{rec.item.price} ({rec.item.name}, {rec.restaurant.name}), above your ₹{req.budget} budget.")
        elif name == "exclusions":
            hints.append(f"Matches exist, but none is tagged free of {', '.join(req.exclude)} in the catalogue.")
        else:
            hints.append(f"Without the {name} filter I'd suggest {rec.item.name} at {rec.restaurant.name} (₹{rec.item.price}).")
    return hints[:3]
