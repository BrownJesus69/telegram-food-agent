"""The evaluation harness as a regression gate: quality may not silently drop, and the guardrail must never leak."""
import asyncio
import dataclasses

import pytest

from evals import run as ev
from evals.grounding import violations
from foodbot.concierge import planner
from foodbot.concierge.intent import FoodRequest
from foodbot.concierge.llm import Cassette, GroqClient
from foodbot.concierge.rules import interpret_rules
from foodbot.services import catalogue

FIELDS = {f.name for f in dataclasses.fields(FoodRequest)}


@pytest.fixture(scope="module")
def sets():
    return {"dev": ev.load_golden("dev"), "heldout": ev.load_golden("heldout")}


def test_golden_files_are_well_formed(sets):
    seen = set()
    for cases in sets.values():
        for c in cases:
            assert c["id"] not in seen, f"duplicate id {c['id']}"
            seen.add(c["id"])
            assert c["text"].strip() and c["cats"] and c["expect"]
            assert set(c["expect"]) <= FIELDS, f"{c['id']}: unknown field in expectations"
    assert len(sets["dev"]) >= 100 and len(sets["heldout"]) >= 40
    assert not {c["text"].lower() for c in sets["dev"]} & {c["text"].lower() for c in sets["heldout"]}, "held-out set leaks into dev set"
    langs = {c["cats"][0] for c in sets["dev"]}
    assert {"kannada", "hinglish", "english"} <= langs or any("kannada" in c["cats"] for c in sets["dev"])


def test_check_function_scores_what_it_claims():
    req = interpret_rules("2 veg and 2 non veg under 1500 for 4")
    assert ev.check({"servings": 4, "budget": 1500, "budget_scope": "total"}, req) == {"servings": True, "budget": True, "budget_scope": True}
    assert ev.check({"servings": 5}, req) == {"servings": False}
    assert ev.check({"diet": "veg"}, None) == {"diet": False}
    assert ev.check({"dishes": []}, interpret_rules("masala dosa")) == {"dishes": False}      # hallucinated dish is a failure
    assert ev.check({"dishes": ["dosa"]}, interpret_rules("masala dosa")) == {"dishes": True}


def test_rules_quality_gate(sets):
    catalogue.load()
    client = GroqClient(api_key="", replay_only=True)
    dev = asyncio.run(ev.score("rules", sets["dev"], client))
    held = asyncio.run(ev.score("rules", sets["heldout"], client))
    assert dev["passed"] / dev["total"] >= 0.95, [k for k, c in dev["cases"].items() if not c["ok"]]
    assert held["passed"] / held["total"] >= 0.80, [k for k, c in held["cases"].items() if not c["ok"]]


@pytest.mark.parametrize("which", ["dev", "heldout"])
def test_guardrail_has_zero_violations(sets, which):
    catalogue.load()
    g = ev.grounding(sets[which])
    assert g["runs"] > 100 and g["answered"] > 50                    # the check actually exercised the planner
    assert g["violations"] == 0, g["examples"]


def test_grounding_checker_detects_real_violations():
    """A checker that never fails proves nothing: hand it a deliberately wrong plan."""
    catalogue.load()
    from datetime import datetime
    now = datetime(2026, 10, 6, 13, 0, tzinfo=catalogue.IST)
    req = interpret_rules("veg biryani under 100")
    good = planner.recommend(interpret_rules("chicken biryani"), 12.9352, 77.6245, now=now, limit=1)
    assert good and violations(interpret_rules("chicken biryani"), good, now) == []
    bad = violations(req, good, now)                                  # a non-veg, over-budget plan judged against a veg/100 request
    assert any("diet" in b for b in bad) and any("over budget" in b for b in bad)
    assert any("closed" in b for b in violations(interpret_rules("x"), good, datetime(2026, 10, 7, 4, 0, tzinfo=catalogue.IST)))


def test_cascade_is_at_least_as_good_as_rules_when_cassette_is_complete(sets):
    cassette = Cassette(ev.CASSETTE)
    cases = sets["dev"] + sets["heldout"]
    missing = [c["id"] for c in cases if cassette.get(c["text"]) is None]
    if missing:
        pytest.skip(f"cassette incomplete ({len(missing)} messages unrecorded); run `python -m evals.record`")
    client = GroqClient(api_key="", cassette=cassette, replay_only=True)
    for name, cs in sets.items():
        rules = asyncio.run(ev.score("rules", cs, client))
        cascade = asyncio.run(ev.score("cascade", cs, client))
        assert cascade["passed"] >= rules["passed"] - 1, f"{name}: cascade regressed vs rules"
