"""The planner may only ever recommend what the catalogue can actually deliver, under every stated constraint."""
import pytest

from evals.grounding import violations
from foodbot.concierge import planner
from foodbot.concierge.rules import interpret_rules
from foodbot.services import catalogue
from foodbot.services.distance import haversine_km

from .conftest import BREAKFAST, KORAMANGALA, LATE, NOON

WHITEFIELD = (12.9698, 77.7500)

REQUESTS = [
    "kuch meetha chahiye", "light dinner for 2 under 500, no onion garlic", "feed 4 people, 2 veg and 2 non veg under 1500",
    "masala dosa and filter coffee", "I am hungry", "something spicy for lunch", "protein rich dinner under 400 per person",
    "chicken biryani under 300", "veg biryani", "gluten free pizza", "south indian breakfast", "sasta chicken biryani",
    "nut allergy something sweet", "jain lunch", "mutton biryani for 6", "paneer under 250 not too spicy", "late night roll",
]


def _assert_grounded(req, recs, now):
    assert violations(req, recs, now) == []


@pytest.mark.parametrize("text", REQUESTS)
@pytest.mark.parametrize("now", [NOON, LATE])
def test_recommendations_never_violate_hard_constraints(text, now):
    req = interpret_rules(text)
    for point in (KORAMANGALA, WHITEFIELD):
        recs = planner.recommend(req, *point, now=now, limit=8, current_slot=catalogue.current_slot(now))
        _assert_grounded(req, recs, now)


def test_group_plan_feeds_every_diet_from_one_kitchen():
    req = interpret_rules("feed 4 people, 2 veg and 2 non veg under 1500")
    recs = planner.recommend(req, *KORAMANGALA, now=NOON, limit=5)
    assert recs
    for rec in recs:
        diets = {ln.item.diet for ln in rec.lines}
        assert "veg" in diets and diets & {"nonveg", "egg"}
        assert sum(ln.qty * planner.serves(ln.item) for ln in rec.lines) >= 4
        assert rec.subtotal <= 1500
        assert rec.subtotal >= rec.restaurant.min_order or any("min order" in r for r in rec.reasons)


def test_bundle_has_every_dish_from_the_same_kitchen():
    req = interpret_rules("masala dosa and filter coffee")
    recs = planner.recommend(req, *KORAMANGALA, now=BREAKFAST, limit=5)
    bundles = [r for r in recs if len(r.lines) > 1]
    assert bundles, "a 9 am bundle of dosa + coffee must exist in Koramangala"
    for rec in bundles:
        names = " ".join(ln.item.name.lower() for ln in rec.lines)
        assert "dosa" in names and "coffee" in names and len({ln.item.restaurant_id for ln in rec.lines}) == 1
        assert "everything from one kitchen" in rec.reasons


def test_serving_size_scales_quantity_and_uses_family_packs():
    req = interpret_rules("chicken biryani for 4")
    recs = planner.recommend(req, *KORAMANGALA, now=NOON, limit=10)
    assert recs
    for rec in recs:
        ln = rec.lines[0]
        assert ln.qty * planner.serves(ln.item) >= 4


def test_sort_preferences_are_honoured():
    base = interpret_rules("chicken biryani")
    cheap = planner.recommend(interpret_rules("cheapest chicken biryani"), *KORAMANGALA, now=NOON, limit=6)
    assert [r.subtotal for r in cheap] == sorted(r.subtotal for r in cheap)
    near = planner.recommend(interpret_rules("nearest chicken biryani"), *KORAMANGALA, now=NOON, limit=6)
    assert [r.distance_km for r in near] == sorted(r.distance_km for r in near)
    assert base.sort == "relevance"


def test_meal_requests_are_not_answered_with_drinks_or_pastries():
    for text in ("I am hungry", "light dinner", "something for lunch"):
        recs = planner.recommend(interpret_rules(text), *KORAMANGALA, now=NOON, limit=10, current_slot="lunch")
        assert recs
        assert not any(planner._is_drink(r.item) or r.item.category in planner.SWEET_SECTIONS for r in recs), text


def test_named_dish_beats_wrong_fuzzy_matches():
    """'biryani' once returned Irani Chai (fuzzy substring). Every hit must really be a biryani."""
    recs = planner.recommend(interpret_rules("biryani"), *KORAMANGALA, now=NOON, limit=20)
    assert recs and all("biryani" in r.item.name.lower() or "biriyani" in " ".join(r.item.aliases) for r in recs)


def test_diagnose_names_the_blocking_constraint():
    where = KORAMANGALA
    h = planner.diagnose(interpret_rules("biryani under 100"), *where, now=NOON)
    assert any("Cheapest match" in x and "₹100" in x for x in h)
    h = planner.diagnose(interpret_rules("idli"), *where, now=LATE)
    assert any("closed right now" in x for x in h)
    h = planner.diagnose(interpret_rules("gluten free pizza"), *where, now=NOON)
    assert any("gluten" in x for x in h)
    far = (13.1189, 77.7267)
    h = planner.diagnose(interpret_rules("masala dosa"), *far, now=NOON)
    assert any("delivery range" in x or "closed" in x for x in h)


def test_distances_reported_are_real():
    recs = planner.recommend(interpret_rules("masala dosa"), *KORAMANGALA, now=NOON, limit=5)
    for r in recs:
        assert r.distance_km == pytest.approx(haversine_km(*KORAMANGALA, r.restaurant.lat, r.restaurant.lon))
