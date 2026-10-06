"""The synthetic catalogue must be valid, reproducible and rich enough for a real Bengaluru customer."""
import csv
import filecmp
import shutil
from collections import Counter
from pathlib import Path

import pytest

from foodbot.services import catalogue
from tools.catalogue_gen import generate
from tools.catalogue_gen.validate import validate

SEED_DIR = Path(__file__).resolve().parents[1] / "seed_data"


def test_committed_catalogue_is_valid():
    assert validate(SEED_DIR) == []


def test_committed_catalogue_matches_generator(tmp_path):
    """seed_data/ must be exactly what `python -m tools.catalogue_gen.generate` produces (no hand edits)."""
    generate.write(generate.build(generate.DEFAULT_SEED), tmp_path, generate.DEFAULT_SEED)
    for name in ("restaurants.csv", "menu.csv", "catalogue_meta.json"):
        assert filecmp.cmp(tmp_path / name, SEED_DIR / name, shallow=False), f"{name} is stale; regenerate it"


def test_generator_is_deterministic_and_seed_sensitive(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    generate.write(generate.build(11), a, 11)
    generate.write(generate.build(11), b, 11)
    assert filecmp.cmp(a / "menu.csv", b / "menu.csv", shallow=False)
    c = tmp_path / "c"
    generate.write(generate.build(12), c, 12)
    assert not filecmp.cmp(a / "menu.csv", c / "menu.csv", shallow=False)
    assert validate(c) == []                      # a different seed is still a valid city


@pytest.mark.parametrize("mutation, expected", [
    (lambda r, m: m[0].update(price="0"), "non-positive price"),
    (lambda r, m: r[0].update(latitude="19.07"), "outside Bengaluru"),
    (lambda r, m: m[1].update(menu_item_id=m[0]["menu_item_id"]), "duplicate menu item id"),
    (lambda r, m: m[2].update(restaurant_id="R9999"), "unknown restaurant"),
    (lambda r, m: r[1].update(name=r[0]["name"]), "duplicate restaurant name"),
    (lambda r, m: m[3].update(veg="1", diet="nonveg"), "veg flag disagrees"),
    (lambda r, m: r[2].update(name="Starbucks"), "banned"),
])
def test_validator_catches_corruption(tmp_path, mutation, expected):
    """A validator that never fails proves nothing: break the data in known ways and expect each to be reported."""
    for name in ("restaurants.csv", "menu.csv"):
        shutil.copy(SEED_DIR / name, tmp_path / name)
    rows = list(csv.DictReader((tmp_path / "restaurants.csv").open(encoding="utf-8")))
    menu = list(csv.DictReader((tmp_path / "menu.csv").open(encoding="utf-8")))
    mutation(rows, menu)
    for fname, data in (("restaurants.csv", rows), ("menu.csv", menu)):
        with (tmp_path / fname).open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, list(data[0].keys()), lineterminator="\n")
            w.writeheader()
            w.writerows(data)
    assert any(expected in e for e in validate(tmp_path))


def test_catalogue_is_rich_enough():
    n_rest, n_items = len(catalogue.RESTAURANTS), len(catalogue.ITEMS)
    assert n_rest >= 450 and n_items >= 10_000
    assert len({i.name for i in catalogue.ITEMS.values()}) >= 450          # the old data had 50
    cats = Counter(r.category for r in catalogue.RESTAURANTS.values())
    assert len(cats) >= 30
    # a Bangalorean's staples are all orderable somewhere
    for staple in ("Benne Masala Dosa", "Bisi Bele Bath", "Thatte Idli", "Filter Coffee", "Mysore Pak", "Donne Chicken Biryani",
                   "Ragi Mudde with Soppu Saaru", "Chow Chow Bath", "Masala Puri", "Bun Maska", "Neer Dosa with Coconut Chutney"):
        assert any(i.name.startswith(staple) for i in catalogue.ITEMS.values()), staple
    # every meal slot and every diet is well represented
    for slot in catalogue.MEAL_SLOTS:
        assert sum(slot in i.slots for i in catalogue.ITEMS.values()) > 1500, slot
    diets = Counter(i.diet for i in catalogue.ITEMS.values())
    assert diets["veg"] > 3000 and diets["nonveg"] > 2500 and diets["egg"] > 100


def test_open_hours_model_midnight_wraparound():
    late = next(r for r in catalogue.RESTAURANTS.values() if r.open_to > 24 * 60 and r.active)
    from datetime import datetime
    assert late.open_at(datetime(2026, 10, 7, 0, 10, tzinfo=catalogue.IST)) or late.open_to <= 24 * 60 + 10
    assert not late.open_at(datetime(2026, 10, 7, 11, 0, tzinfo=catalogue.IST)) or late.open_from <= 11 * 60
