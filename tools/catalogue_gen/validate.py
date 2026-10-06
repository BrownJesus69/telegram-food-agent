"""Validate a generated catalogue directory. Returns a list of human-readable problems (empty == valid).

    python -m tools.catalogue_gen.validate            # validates seed_data/
"""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from tools.catalogue_gen.archetypes import BANNED_NAMES
from tools.catalogue_gen.generate import (
    COVERAGE_NEED,
    OUT_DIR,
    SLOT_PROBE,
    open_at,
)
from tools.catalogue_gen.localities import LOCALITIES

BENGALURU_BBOX = (12.80, 13.16, 77.45, 77.80)      # lat_min, lat_max, lon_min, lon_max
VALID_DIETS = {"veg", "egg", "nonveg"}
VALID_SLOTS = {"breakfast", "lunch", "snack", "dinner", "latenight"}
HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _km(a_lat, a_lon, b_lat, b_lon) -> float:
    from tools.catalogue_gen.generate import _km as km
    return km(a_lat, a_lon, b_lat, b_lon)


def validate(data_dir: Path = OUT_DIR) -> list[str]:
    errors: list[str] = []
    rests = list(csv.DictReader((data_dir / "restaurants.csv").open(encoding="utf-8")))
    menu = list(csv.DictReader((data_dir / "menu.csv").open(encoding="utf-8")))

    rid_set = set()
    names = Counter()
    for r in rests:
        rid = r["restaurant_id"]
        if rid in rid_set:
            errors.append(f"duplicate restaurant id {rid}")
        rid_set.add(rid)
        names[r["name"].lower()] += 1
        if r["name"].lower() in BANNED_NAMES:
            errors.append(f"{rid}: banned (real-brand) name {r['name']!r}")
        lat, lon = float(r["latitude"]), float(r["longitude"])
        if not (BENGALURU_BBOX[0] <= lat <= BENGALURU_BBOX[1] and BENGALURU_BBOX[2] <= lon <= BENGALURU_BBOX[3]):
            errors.append(f"{rid}: coordinates outside Bengaluru ({lat}, {lon})")
        for col in ("open_from", "open_to"):
            if not HHMM.match(r[col]):
                errors.append(f"{rid}: bad {col} {r[col]!r}")
        if not (3.0 <= float(r["catalogue_rating"]) <= 5.0):
            errors.append(f"{rid}: rating out of range")
        if int(r["delivery_fee"]) < 0 or int(r["min_order"]) < 0:
            errors.append(f"{rid}: negative fee/min order")
        if not (1.0 <= float(r["radius_km"]) <= 10.0):
            errors.append(f"{rid}: implausible radius {r['radius_km']}")
        if r["active"] not in ("0", "1"):
            errors.append(f"{rid}: active must be 0/1")
    for n, c in names.items():
        if c > 1:
            errors.append(f"duplicate restaurant name {n!r} x{c}")

    items_by_rest: dict[str, list[dict]] = defaultdict(list)
    item_ids = set()
    for m in menu:
        iid = m["menu_item_id"]
        if iid in item_ids:
            errors.append(f"duplicate menu item id {iid}")
        item_ids.add(iid)
        if m["restaurant_id"] not in rid_set:
            errors.append(f"{iid}: unknown restaurant {m['restaurant_id']}")
        items_by_rest[m["restaurant_id"]].append(m)
        if int(m["price"]) <= 0:
            errors.append(f"{iid}: non-positive price")
        if m["diet"] not in VALID_DIETS:
            errors.append(f"{iid}: bad diet {m['diet']!r}")
        if (m["veg"] == "1") != (m["diet"] == "veg"):
            errors.append(f"{iid}: veg flag disagrees with diet")
        if not 0 <= int(m["spice"]) <= 3:
            errors.append(f"{iid}: spice out of range")
        slots = set(filter(None, m["meal_slots"].split("|")))
        if not slots or not slots <= VALID_SLOTS:
            errors.append(f"{iid}: bad meal_slots {m['meal_slots']!r}")
        if not m["item_description"].strip():
            errors.append(f"{iid}: empty description")

    pure_veg_ids = {r["restaurant_id"] for r in rests if "pure-veg" in r["tags"].split("|")}
    for r in rests:
        its = items_by_rest.get(r["restaurant_id"], [])
        if len(its) < 8:
            errors.append(f"{r['restaurant_id']}: only {len(its)} menu items")
        seen = Counter(i["item_name"] for i in its)
        for name, c in seen.items():
            if c > 1:
                errors.append(f"{r['restaurant_id']}: duplicate item {name!r}")
        if r["restaurant_id"] in pure_veg_ids and any(i["diet"] != "veg" for i in its):
            errors.append(f"{r['restaurant_id']}: tagged pure-veg but serves egg/non-veg")

    # coverage: every neighbourhood must have real choice at every meal, as a customer would expect
    for loc in LOCALITIES:
        near = [r for r in rests if r["active"] == "1" and _km(loc.lat, loc.lon, float(r["latitude"]), float(r["longitude"])) <= 3.0]
        for slot, need in COVERAGE_NEED.items():
            n = 0
            for r in near:
                if open_at(r["open_from"], r["open_to"], SLOT_PROBE[slot]) and any(
                    slot in i["meal_slots"].split("|") and i["in_stock"] == "1" for i in items_by_rest[r["restaurant_id"]]
                ):
                    n += 1
            if n < need:
                errors.append(f"coverage: {loc.name} has {n} {slot} options within 3 km (need {need})")
    return errors


def main() -> int:
    errs = validate(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT_DIR)
    for e in errs[:50]:
        print("ERROR:", e)
    print(f"{len(errs)} problem(s)")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
