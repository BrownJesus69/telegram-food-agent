"""Generate the synthetic Bengaluru catalogue (restaurants.csv + menu.csv).

Deterministic: the same seed always yields byte-identical files.

    python -m tools.catalogue_gen.generate            # writes seed_data/
    python -m tools.catalogue_gen.generate --seed 7   # a different but equally valid city
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from tools.catalogue_gen import dishes_north, dishes_other, dishes_south
from tools.catalogue_gen.archetypes import ARCHETYPES, BANNED_NAMES, Archetype
from tools.catalogue_gen.dsl import Dish
from tools.catalogue_gen.localities import LOCALITIES, Locality

DEFAULT_SEED = 20261006
OUT_DIR = Path(__file__).resolve().parents[2] / "seed_data"

ALL_DISHES: list[Dish] = dishes_south.DISHES + dishes_north.DISHES + dishes_other.DISHES
DISHES_BY_FAMILY: dict[str, list[Dish]] = defaultdict(list)
for _d in ALL_DISHES:
    for _f in _d.families:
        DISHES_BY_FAMILY[_f].append(_d)

# Local-time windows (minutes after midnight) for each meal slot. latenight wraps past midnight.
SLOT_WINDOWS = {
    "breakfast": (6 * 60, 11 * 60),
    "lunch": (11 * 60, 15 * 60 + 30),
    "snack": (15 * 60 + 30, 18 * 60 + 30),
    "dinner": (18 * 60 + 30, 23 * 60),
    "latenight": (23 * 60, 30 * 60),   # 23:00 -> 06:00 next day
}
SLOT_PROBE = {"breakfast": 8 * 60 + 30, "lunch": 13 * 60, "snack": 17 * 60, "dinner": 20 * 60 + 30, "latenight": 24 * 60 + 30}
LEVEL_MULT = {1: 0.82, 2: 1.0, 3: 1.32}
FEE_BY_LEVEL = {1: [0, 15, 20, 25], 2: [20, 25, 30, 35, 40], 3: [30, 35, 45, 49, 59]}
MIN_ORDER_BY_LEVEL = {1: [0, 0, 79, 99], 2: [0, 99, 149, 149], 3: [149, 199, 249]}


def hm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def window(open_s: str, close_s: str) -> tuple[int, int]:
    o, c = hm(open_s), hm(close_s)
    if c <= o:
        c += 24 * 60
    return o, c


def overlaps(open_s: str, close_s: str, slot: str) -> bool:
    o, c = window(open_s, close_s)
    a, b = SLOT_WINDOWS[slot]
    for shift in (0, 24 * 60):          # compare against today's and tomorrow's copy of the slot
        if o < b + shift and a + shift < c:
            return True
    return False


def open_at(open_s: str, close_s: str, minute_of_day: int) -> bool:
    o, c = window(open_s, close_s)
    return any(o <= minute_of_day + s < c for s in (0, 24 * 60))


# ------------------------------------------------------------------ allergens
_ALLERGEN_RULES = {
    "dairy": r"paneer|cheese|butter|cream|curd|raita|lassi|milk|kulfi|ice cream|ghee|malai|rabri|rabdi|rasmalai|rasgulla|sandesh|kheer|payasam|doi|shake|latte|cappuccino|mocha|flat white|chocolate|cheesecake|tiramisu|pastry|cake|pancake|alfredo|brioche|croissant|muffin|waffle|gelato|sundae|falooda|khoya|halwa|pedha|burfi|laddu|kaju",
    "gluten": r"roti|naan|paratha|parotta|bread|bun|pav|pizza|burger|pasta|penne|noodles|ramen|momo|dumpling|dimsum|dim sum|puff|cake|pastry|croissant|biscuit|cookie|sandwich|wrap|puri|bhatura|kulcha|samosa|kachori|rusk|doughnut|muffin|waffle|pancake|lasagna|bruschetta|toast|rava|semolina|upma|cutlet|nugget|manchurian|spring roll|gyoza|bao|tortilla|nachos|rolls?\b|baati|thepla|luchi|bonda|mandi|chakli",
    "egg": r"\begg|omelette|omelet|bhurji|mayo|shakshuka|benedict|tiramisu",
    "nuts": r"cashew|almond|badam|pista|walnut|kaju|nuts|dry fruit|korma|shahi|baklava|pesto",
    "peanut": r"peanut|groundnut|pad thai|ennegayi|khara bath|chow chow",
    "fish": r"fish|prawn|crab|squid|calamari|seafood|surmai|pomfret|anjal|mackerel|apollo|ilish|hilsa|rohu|chingri|chemmeen|meen|bangude|kane|tom yum",
    "soy": r"soy|manchurian|schezwan|hakka|fried rice|noodles|chilli|dimsum|dim sum|teriyaki|miso|ramen|bibimbap|kimchi",
    "sesame": r"sesame|tahini|hummus|baba|til\b|bibimbap|podi|gyoza",
}


def infer_allergens(d: Dish) -> list[str]:
    text = f"{d.name} {d.desc}".lower()
    found = [a for a, rx in _ALLERGEN_RULES.items() if re.search(rx, text)]
    if d.diet == "egg" and "egg" not in found:
        found.append("egg")
    return sorted(set(found))


# ------------------------------------------------------------------ restaurants
@dataclass
class Rest:
    arch: Archetype
    locality: Locality
    name: str
    lat: float
    lon: float
    address: str
    open_s: str
    close_s: str
    level: int
    radius: float
    prep: int
    fee: int
    min_order: int
    rating: float
    rating_count: int
    active: int
    menu: list[tuple[Dish, int, int]] = field(default_factory=list)   # (dish, price, in_stock)
    tags: list[str] = field(default_factory=list)
    rid: str = ""


def _weighted(rng: random.Random, options):
    values = [o[:-1] if len(o) > 2 else o[0] for o in options]
    weights = [o[-1] for o in options]
    return rng.choices(values, weights=weights, k=1)[0]


def _offset(rng: random.Random, loc: Locality) -> tuple[float, float]:
    r = min(1.6, abs(rng.gauss(0, 0.65)))            # km from the locality centre
    ang = rng.uniform(0, 2 * math.pi)
    dlat = r * math.cos(ang) / 111.0
    dlon = r * math.sin(ang) / (111.0 * math.cos(math.radians(loc.lat)))
    return round(loc.lat + dlat, 6), round(loc.lon + dlon, 6)


def _round5(x: float) -> int:
    return max(10, int(round(x / 5.0)) * 5)


def _unique_name(rng: random.Random, arch: Archetype, taken: set[str]) -> str:
    for _ in range(200):
        name = f"{rng.choice(arch.prefixes)} {rng.choice(arch.suffixes)}"
        words = [w.lower() for w in name.split()]
        if len(set(words)) != len(words):
            continue
        if name.lower() in taken or name.lower() in BANNED_NAMES:
            continue
        return name
    raise RuntimeError(f"ran out of unique names for {arch.key}")


def _pick_menu(rng: random.Random, arch: Archetype, open_s: str, close_s: str) -> list[Dish]:
    veg_only = "pure-veg" in arch.tags

    def eligible(d: Dish) -> bool:
        if veg_only and d.diet != "veg":
            return False
        return any(overlaps(open_s, close_s, s) for s in d.slots)

    chosen: dict[str, Dish] = {}
    for fam in arch.core:
        for d in DISHES_BY_FAMILY[fam]:
            if eligible(d) and rng.random() < 0.82:
                chosen.setdefault(d.name, d)
    for fam in arch.extra:
        for d in DISHES_BY_FAMILY[fam]:
            if eligible(d) and rng.random() < 0.30:
                chosen.setdefault(d.name, d)

    lo, hi = arch.menu_size
    target = rng.randint(lo, hi)
    items = list(chosen.values())
    if len(items) > target:
        def priority(d: Dish) -> float:
            boost = 2.0 if "bestseller" in d.tags else 0.0
            boost += 1.5 if "must-try" in d.tags else 0.0
            return boost + rng.random()
        items = sorted(items, key=priority, reverse=True)[:target]
    elif len(items) < lo:                                        # top up from extra/core at p=1
        pool = [d for fam in arch.core + arch.extra for d in DISHES_BY_FAMILY[fam] if eligible(d) and d.name not in chosen]
        rng.shuffle(pool)
        for d in pool[: lo - len(items)]:
            items.append(d)
            chosen[d.name] = d

    have = {d.name for d in items}
    for fam, k in arch.drinks:
        pool = [d for d in DISHES_BY_FAMILY[fam] if eligible(d) and d.name not in have]
        rng.shuffle(pool)
        for d in pool[:k]:
            items.append(d)
            have.add(d.name)
    return items


def _make_restaurant(rng: random.Random, arch: Archetype, loc: Locality, taken: set[str]) -> Rest:
    open_s, close_s = _weighted(rng, arch.hours)
    level = _weighted(rng, arch.price_levels)
    name = _unique_name(rng, arch, taken)
    taken.add(name.lower())
    lat, lon = _offset(rng, loc)
    street = rng.choice(loc.streets)
    address = f"No. {rng.randint(1, 260)}, {street}, {loc.name}, Bengaluru - {loc.pincode}"
    rating = round(min(4.9, max(3.3, rng.gauss(arch.rating_mean, 0.25))), 1)
    rating_count = int(min(9000, max(12, rng.lognormvariate(5.2, 0.9))))
    r = Rest(
        arch=arch, locality=loc, name=name, lat=lat, lon=lon, address=address,
        open_s=open_s, close_s=close_s, level=level,
        radius=round(rng.uniform(*arch.radius), 1),
        prep=rng.randint(*arch.prep),
        fee=rng.choice(FEE_BY_LEVEL[level]),
        min_order=rng.choice(MIN_ORDER_BY_LEVEL[level]),
        rating=rating, rating_count=rating_count,
        active=0 if rng.random() < 0.03 else 1,
    )
    mult = LEVEL_MULT[level] * loc.premium
    for d in _pick_menu(rng, arch, open_s, close_s):
        price = _round5(d.price * mult * (1 + rng.uniform(-0.06, 0.08)))
        r.menu.append((d, price, 0 if rng.random() < 0.03 else 1))
    r.tags = list(arch.tags)
    if all(d.diet == "veg" for d, _, _ in r.menu) and "pure-veg" not in r.tags:
        r.tags.append("pure-veg")
    if level == 1 and "budget" not in r.tags:
        r.tags.append("budget")
    if rating >= 4.4:
        r.tags.append("top-rated")
    return r


def _weighted_locality(rng: random.Random) -> Locality:
    return rng.choices(LOCALITIES, weights=[loc.weight for loc in LOCALITIES], k=1)[0]


def _km(a_lat, a_lon, b_lat, b_lon) -> float:
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(h))


def _serving(r: Rest, slot: str) -> bool:
    return bool(r.active) and open_at(r.open_s, r.close_s, SLOT_PROBE[slot]) and any(
        slot in d.slots and st for d, _, st in r.menu
    )


def coverage_gaps(rests: list[Rest], need: dict[str, int]) -> list[tuple[Locality, str]]:
    gaps = []
    for loc in LOCALITIES:
        near = [r for r in rests if _km(loc.lat, loc.lon, r.lat, r.lon) <= 3.0]
        for slot, n in need.items():
            if sum(_serving(r, slot) for r in near) < n:
                gaps.append((loc, slot))
        if sum(1 for r in rests if r.locality is loc) < 6:
            gaps.append((loc, "dinner"))
    return gaps


FILLER_FOR_SLOT = {
    "breakfast": "breakfast_corner", "lunch": "karnataka_meals", "snack": "chaat_corner",
    "dinner": "north_dhaba", "latenight": "late_night",
}
COVERAGE_NEED = {"breakfast": 5, "lunch": 8, "snack": 6, "dinner": 8, "latenight": 2}


def build(seed: int = DEFAULT_SEED) -> list[Rest]:
    rng = random.Random(seed)
    taken: set[str] = set()
    rests: list[Rest] = []
    for arch in ARCHETYPES:
        for _ in range(arch.count):
            rests.append(_make_restaurant(rng, arch, _weighted_locality(rng), taken))

    arch_by_key = {a.key: a for a in ARCHETYPES}
    for _ in range(6):                                  # repair loop: fill coverage gaps deterministically
        gaps = coverage_gaps(rests, COVERAGE_NEED)
        if not gaps:
            break
        for loc, slot in gaps:
            rests.append(_make_restaurant(rng, arch_by_key[FILLER_FOR_SLOT[slot]], loc, taken))
    else:
        raise RuntimeError("coverage repair did not converge")

    rests.sort(key=lambda r: (r.locality.name, r.arch.key, r.name))
    for i, r in enumerate(rests, start=1):
        r.rid = f"R{i:04d}"
    return rests


# --------------------------------------------------------------------- output
RESTAURANT_FIELDS = [
    "restaurant_id", "name", "locality", "latitude", "longitude", "address", "category", "cuisine",
    "price_level", "catalogue_rating", "rating_count", "prep_minutes", "delivery_fee", "min_order",
    "radius_km", "open_from", "open_to", "tags", "active", "operator_chat_id", "operator_mode",
]
MENU_FIELDS = [
    "menu_item_id", "restaurant_id", "restaurant_name", "item_name", "item_description", "category",
    "veg", "diet", "spice", "meal_slots", "tags", "allergens", "calories", "price", "currency",
    "in_stock", "prep_minutes", "tax_rate", "active", "aliases",
]


def write(rests: list[Rest], out_dir: Path, seed: int) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    n_items = 0
    with (out_dir / "restaurants.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, RESTAURANT_FIELDS, lineterminator="\n")
        w.writeheader()
        for r in rests:
            w.writerow({
                "restaurant_id": r.rid, "name": r.name, "locality": r.locality.name,
                "latitude": r.lat, "longitude": r.lon, "address": r.address,
                "category": r.arch.label, "cuisine": r.arch.cuisine, "price_level": r.level,
                "catalogue_rating": r.rating, "rating_count": r.rating_count, "prep_minutes": r.prep,
                "delivery_fee": r.fee, "min_order": r.min_order, "radius_km": r.radius,
                "open_from": r.open_s, "open_to": r.close_s, "tags": "|".join(r.tags), "active": r.active,
                "operator_chat_id": "", "operator_mode": "SIMULATED",
            })
    with (out_dir / "menu.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, MENU_FIELDS, lineterminator="\n")
        w.writeheader()
        for r in rests:
            for d, price, in_stock in r.menu:
                n_items += 1
                w.writerow({
                    "menu_item_id": f"M{n_items:06d}", "restaurant_id": r.rid, "restaurant_name": r.name,
                    "item_name": d.name, "item_description": d.desc, "category": d.section,
                    "veg": 1 if d.diet == "veg" else 0, "diet": d.diet, "spice": d.spice,
                    "meal_slots": "|".join(d.slots), "tags": "|".join(d.tags),
                    "allergens": "|".join(infer_allergens(d)), "calories": d.kcal, "price": price,
                    "currency": "INR", "in_stock": in_stock, "prep_minutes": d.prep, "tax_rate": 0.05,
                    "active": 1, "aliases": "|".join(d.aliases),
                })
    stats = {
        "seed": seed,
        "restaurants": len(rests),
        "menu_items": n_items,
        "distinct_dishes": len({d.name for r in rests for d, _, _ in r.menu}),
        "localities": len({r.locality.name for r in rests}),
        "archetypes": dict(Counter(r.arch.key for r in rests)),
        "note": "Synthetic data. Restaurant names, menus and prices are invented; locality coordinates are approximate.",
    }
    (out_dir / "catalogue_meta.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    return stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args()
    rests = build(args.seed)
    stats = write(rests, args.out, args.seed)
    print(json.dumps({k: v for k, v in stats.items() if k != "archetypes"}, indent=2))


if __name__ == "__main__":
    main()
