"""Property-based tests (Hypothesis): the guarantees must hold for inputs nobody thought to write down.

The README claims "the LLM proposes, deterministic code disposes". These tests attack that claim with random and
hostile model replies, random text, and random requests against the planner (see docs/adr/0002-llm-boundary.md).
"""
import os
from datetime import datetime, timedelta

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from evals.grounding import schema_problems, violations
from foodbot.concierge import intent, planner
from foodbot.concierge.intent import FoodRequest, Group
from foodbot.concierge.rules import DISH_MAP, interpret_rules
from foodbot.concierge.understand import merge, normalise_llm
from foodbot.services import catalogue

EXPLORE = bool(os.environ.get("EXPLORE"))       # EXPLORE=1 pytest tests/test_properties.py : fresh random inputs each run
SLOW = settings(max_examples=120, deadline=None, derandomize=not EXPLORE, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
FAST = settings(max_examples=300, deadline=None, derandomize=not EXPLORE, suppress_health_check=[HealthCheck.too_slow])


# ---------------------------------------------------------------- strategies
json_leaf = st.none() | st.booleans() | st.integers(-10**12, 10**12) | st.floats(allow_nan=True, allow_infinity=True) | st.text(max_size=80)
json_value = st.recursive(json_leaf, lambda c: st.lists(c, max_size=5) | st.dictionaries(st.text(max_size=12), c, max_size=5), max_leaves=12)

REPLY_KEYS = ["intent", "dishes", "combine", "cuisine", "slot", "diet", "exclude", "tags", "spice", "budget", "budget_scope",
              "servings", "quantity", "groups", "sort", "restaurant", "language"]


def _vocab_or_junk(vocab):
    return st.sampled_from(list(vocab)) | json_value


hostile_reply = st.fixed_dictionaries({}, optional={
    "intent": _vocab_or_junk(intent.INTENTS), "dishes": json_value | st.lists(st.text(max_size=90), max_size=8),
    "combine": json_value, "cuisine": _vocab_or_junk(intent.CUISINES), "slot": _vocab_or_junk(intent.SLOTS),
    "diet": _vocab_or_junk(intent.DIETS + ("non-veg", "vegetarian", "NONVEG")), "exclude": json_value | st.lists(_vocab_or_junk(intent.EXCLUDES), max_size=6),
    "tags": json_value | st.lists(_vocab_or_junk(intent.TAGS), max_size=6), "spice": _vocab_or_junk(intent.SPICES),
    "budget": json_value, "budget_scope": _vocab_or_junk(intent.SCOPES), "servings": json_value, "quantity": json_value,
    "groups": json_value | st.lists(st.fixed_dictionaries({"diet": _vocab_or_junk(intent.DIETS), "count": json_value}), max_size=5),
    "sort": _vocab_or_junk(intent.SORTS), "restaurant": json_value, "language": _vocab_or_junk(intent.LANGS),
}).map(lambda d: {**d, "__proto__": {"admin": True}, "price": 1, "total": 0})        # plus keys the schema never allowed


def assert_in_vocabulary(req: FoodRequest):
    assert schema_problems(req) == []


# ---------------------------------------------------------------- the LLM boundary
@FAST
@given(hostile_reply)
def test_any_model_reply_becomes_a_valid_request(reply):
    assert_in_vocabulary(intent.from_dict(reply, raw="x"))


@FAST
@given(json_value)
def test_even_non_object_replies_are_survivable(reply):
    assert_in_vocabulary(intent.from_dict(reply, raw="x"))


@FAST
@given(hostile_reply, st.text(max_size=120))
def test_normalising_a_hostile_reply_stays_in_vocabulary(reply, text):
    assert_in_vocabulary(normalise_llm(intent.from_dict(reply, raw=text), text))


STATED = st.builds(
    lambda diet, excl, budget: (diet, excl, budget),
    st.sampled_from([None, "veg", "vegetarian", "non veg", "pure veg"]),
    st.lists(st.sampled_from(["peanuts", "dairy", "gluten", "onion", "fish", "soy", "sesame", "nuts"]), max_size=2, unique=True),
    st.sampled_from([None, 80, 150, 300, 1200]),
)


def _sentence(diet, excl, budget) -> str:
    bits = ["something good"]
    if diet:
        bits.append(f"i am {diet}")
    if excl:
        bits.append("allergic to " + " and ".join(excl))
    if budget:
        bits.append(f"under {budget}")
    return ", ".join(bits)


@FAST
@given(STATED, hostile_reply)
def test_a_model_can_never_overrule_what_the_customer_stated(stated, reply):
    """Diet, allergies and budget the customer typed survive any model reading (hallucinated or injected)."""
    text = _sentence(*stated)
    rules = interpret_rules(text)
    got = merge(normalise_llm(intent.from_dict(reply, raw=text), text), rules)
    assert_in_vocabulary(got)
    if rules.diet:
        assert got.diet == rules.diet
    assert set(rules.exclude) <= set(got.exclude)
    if rules.budget:
        assert got.budget == rules.budget
        # a party size the model found can only make the scope stricter ("item" -> "total"), never looser
        assert got.budget_scope == rules.budget_scope or (rules.budget_scope == "item" and got.budget_scope == "total" and got.servings > 1)


# ---------------------------------------------------------------- the rules
NOISE = st.sampled_from(["please", "pls", "hungry", "now", "today", "tasty", "really", "yaar", "bhaiya"])


@FAST
@given(st.text(max_size=300))
def test_rules_handle_any_text(text):
    req = interpret_rules(text)
    assert_in_vocabulary(req)
    assert interpret_rules(text).to_dict() == req.to_dict(), "interpretation must be deterministic"


@FAST
@given(st.text(alphabet=list("abcdefgnovegx ,.-&+₹0123456789\n<>/'\"éಒಂದು‮"), max_size=200))
def test_rules_handle_tokenish_text(text):
    assert_in_vocabulary(interpret_rules(text))


@FAST
@given(STATED, st.lists(NOISE, max_size=4), st.lists(NOISE, max_size=4))
def test_filler_words_do_not_change_stated_constraints(stated, before, after):
    plain = interpret_rules(_sentence(*stated))
    noisy = interpret_rules(" ".join(before) + " " + _sentence(*stated) + " " + " ".join(after))
    assert (noisy.diet, set(noisy.exclude), noisy.budget) == (plain.diet, set(plain.exclude), plain.budget)


# ---------------------------------------------------------------- the planner (the guardrail)
DISH_WORDS = sorted({v for v in DISH_MAP.values() if v} | {"biryani", "dosa", "idli", "pizza", "burger", "paneer", "chicken", "coffee",
                                                          "thali", "noodles", "sandwich", "cake", "meals", "momos", "roll"})


def _sometimes(strategy, odds: int = 3):
    """Mostly None: a request with every constraint at once matches nothing, which would make the guardrail test vacuous."""
    return st.one_of(*([st.none()] * odds), strategy)


@st.composite
def requests(draw):
    groups = []
    if draw(st.integers(0, 9)) == 0:
        groups = [Group("veg", draw(st.integers(1, 4))), Group("nonveg", draw(st.integers(1, 4)))]
    return FoodRequest(
        dishes=draw(st.lists(st.sampled_from(DISH_WORDS), max_size=2, unique=True) if draw(st.booleans()) else st.just([])),
        cuisine=draw(_sometimes(st.sampled_from(intent.CUISINES), 6)),
        slot=draw(_sometimes(st.sampled_from(intent.SLOTS), 3)),
        diet=draw(_sometimes(st.sampled_from(intent.DIETS), 2)),
        exclude=draw(st.one_of(st.just([]), st.just([]), st.lists(st.sampled_from(intent.EXCLUDES), min_size=1, max_size=2, unique=True))),
        tags=draw(st.one_of(st.just([]), st.just([]), st.lists(st.sampled_from(intent.TAGS), min_size=1, max_size=2, unique=True))),
        spice=draw(_sometimes(st.sampled_from(intent.SPICES), 4)),
        budget=draw(_sometimes(st.integers(60, 3000), 2)),
        budget_scope=draw(st.sampled_from(intent.SCOPES)),
        servings=draw(st.integers(1, 4)), quantity=draw(st.integers(1, 3)), groups=groups,
        sort=draw(st.sampled_from(intent.SORTS)), combine=draw(st.booleans()),
    ).clean()


bengaluru = st.tuples(st.floats(12.90, 13.05), st.floats(77.55, 77.70))      # the dense middle of the city
moments = st.integers(0, 24 * 4 - 1).map(lambda q: datetime(2026, 10, 6, tzinfo=catalogue.IST) + timedelta(minutes=15 * q))


@SLOW
@given(requests(), bengaluru, moments)
def test_the_planner_never_breaks_a_hard_constraint(req, point, now):
    recs = planner.recommend(req, *point, now=now, limit=6, current_slot=catalogue.current_slot(now))
    assert violations(req, recs, now) == []


def test_the_guardrail_test_is_not_vacuous():
    """Test the test: most random requests must produce answers, or 'no violations' would prove nothing."""
    seen = {"n": 0, "answered": 0}

    @settings(max_examples=120, deadline=None, derandomize=True, suppress_health_check=[HealthCheck.too_slow])
    @given(requests(), bengaluru, moments)
    def run(req, point, now):
        recs = planner.recommend(req, *point, now=now, limit=6, current_slot=catalogue.current_slot(now))
        seen["n"] += 1
        seen["answered"] += bool(recs)

    run()
    assert seen["answered"] >= 0.3 * seen["n"], seen


@SLOW
@given(requests(), bengaluru, moments)
def test_diagnosis_never_raises_and_only_speaks_in_plain_text(req, point, now):
    hints = planner.diagnose(req, *point, now=now, current_slot=catalogue.current_slot(now))
    assert all(isinstance(h, str) and h for h in hints)
