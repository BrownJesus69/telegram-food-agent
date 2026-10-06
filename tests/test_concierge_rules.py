"""The deterministic interpreter: what it extracts, and what it must never invent."""
import pytest

from foodbot.concierge.intent import FoodRequest, from_dict
from foodbot.concierge.rules import interpret_rules


def test_budget_scope_and_quantity():
    r = interpret_rules("I am hungry, I want Shawarma under 200")
    assert (r.dishes, r.budget, r.budget_scope, r.quantity) == (["shawarma"], 200, "item", 1)
    r = interpret_rules("2 chicken shawarma below rs 300")
    assert (r.dishes, r.budget, r.quantity) == (["chicken shawarma"], 300, 2)
    r = interpret_rules("dinner for 4 under 1500 total")
    assert (r.servings, r.budget, r.budget_scope, r.slot) == (4, 1500, "total", "dinner")
    r = interpret_rules("protein rich dinner under 400 per person")
    assert r.budget_scope == "per_person" and "high-protein" in r.tags


def test_mixed_diet_groups_need_two_diets():
    r = interpret_rules("feed 4 people, 2 veg and 2 non veg under 1200")
    assert {(g.diet, g.count) for g in r.groups} == {("veg", 2), ("nonveg", 2)}
    assert r.servings == 4 and r.budget_scope == "total" and r.dishes == []
    assert interpret_rules("2 veg burgers").groups == []                  # one diet is just a quantity


@pytest.mark.parametrize("text, exclude", [
    ("light dinner no onion garlic", ["onion-garlic"]),
    ("jain breakfast", ["onion-garlic"]),
    ("I have a nut allergy, want something sweet", ["nuts"]),
    ("gluten free pizza", ["gluten"]),
    ("dairy free dessert", ["dairy"]),
    ("biryani without egg", ["egg"]),
])
def test_exclusions(text, exclude):
    assert interpret_rules(text).exclude == exclude


@pytest.mark.parametrize("text, lang", [
    ("ondu masala dose", "kn"), ("kuch meetha chahiye", "hi"), ("hasivu aagide, swalpa khara tindi beku", "kn"),
    ("mujhe biryani chahiye, ondu plate", "mixed"), ("chicken biryani please", "en"),
])
def test_language_detection(text, lang):
    assert interpret_rules(text).language == lang


def test_kannada_and_hinglish_words_map_to_catalogue_vocabulary():
    assert interpret_rules("ondu masala dose").dishes == ["masala dosa"]
    assert interpret_rules("kodi biriyani").dishes == ["chicken biryani"]
    assert interpret_rules("filter kaapi").dishes == ["filter coffee"]
    r = interpret_rules("kuch meetha")
    assert r.dishes == [] and r.tags == ["sweet"]
    assert interpret_rules("veg alla, biryani beku").diet == "nonveg"


def test_combine_vs_alternatives():
    r = interpret_rules("masala dosa and filter coffee")
    assert r.dishes == ["masala dosa", "filter coffee"] and r.combine
    r = interpret_rules("chicken biryani or mutton biryani")
    assert r.dishes == ["chicken biryani", "mutton biryani"] and not r.combine


def test_sort_slot_spice_tags():
    r = interpret_rules("sasta chicken biryani jaldi")
    assert r.sort == "cheapest" and r.dishes == ["chicken biryani"]
    assert interpret_rules("something spicy for lunch").spice == "hot"
    assert interpret_rules("not too spicy curry").spice == "mild"
    assert interpret_rules("late night chicken roll").slot == "latenight"
    assert interpret_rules("south indian breakfast near me").cuisine == "south indian"


@pytest.mark.parametrize("text, intent", [("hi", "greeting"), ("Namaskara", "greeting"), ("thanks!", "other"), ("show cart", "cart")])
def test_non_order_intents(text, intent):
    assert interpret_rules(text).intent == intent


def test_describe_is_a_faithful_echo():
    d = interpret_rules("light dinner for 2 under 500, no onion garlic").describe()
    for part in ("dinner", "light", "for 2", "₹500", "total", "no onion-garlic"):
        assert part in d


# ---- the validation boundary: whatever a model returns, the request stays inside the vocabulary
def test_from_dict_coerces_untrusted_input():
    r = from_dict({
        "intent": "DROP TABLE users", "dishes": ["  Masala Dosa  ", "x" * 500, ""], "diet": "vegan", "slot": "teatime",
        "exclude": ["nuts", "bleach"], "tags": ["sweet", "free-money"], "spice": "nuclear", "budget": "ten million",
        "budget_scope": "whatever", "servings": 9999, "quantity": -3, "sort": "random", "language": "klingon",
        "groups": [{"diet": "veg", "count": 2}, {"diet": "poison", "count": 5}], "price": 0, "restaurant": "A" * 300,
    })
    assert r.intent == "order" and r.diet is None and r.slot is None and r.spice is None and r.budget is None
    assert r.exclude == ["nuts"] and r.tags == ["sweet"] and r.budget_scope == "item" and r.sort == "relevance"
    assert r.servings == 20 and r.quantity == 1 and r.language is None and r.groups == []
    assert r.dishes[0] == "masala dosa" and all(len(d) <= 60 for d in r.dishes) and len(r.restaurant) <= 60


def test_from_dict_tolerates_garbage_shapes():
    for junk in (None, [], "text", 42, {"dishes": 5, "groups": "x", "exclude": 3, "tags": None}):
        assert isinstance(from_dict(junk), FoodRequest)


def test_other_intent_with_a_target_is_an_order():
    assert from_dict({"intent": "other", "tags": ["sweet"]}).intent == "order"
