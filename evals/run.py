"""Score the concierge against the golden set.

    python -m evals.run                 # rules, llm (replayed), cascade and full pipeline, plus grounding
    python -m evals.run --out evals/RESULTS.md

LLM numbers come from recorded replies (evals/cassette.json), so a run is offline, free and deterministic.
Re-record with `python -m evals.record` after changing the prompt or schema.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
from collections import defaultdict
from pathlib import Path

from evals.grounding import violations
from foodbot.concierge import planner
from foodbot.concierge.intent import FoodRequest
from foodbot.concierge.llm import Cassette, GroqClient
from foodbot.concierge.rules import interpret_rules
from foodbot.concierge.understand import normalise_llm, second_opinion, understand
from foodbot.services import catalogue

HERE = Path(__file__).resolve().parent
GOLDEN = HERE / "golden.jsonl"            # dev set: used while building the rules
HELDOUT = HERE / "heldout.jsonl"          # written afterwards and never tuned to
CASSETTE = HERE / "cassette.json"

KORAMANGALA = (12.9352, 77.6245)
WHITEFIELD = (12.9698, 77.7500)
TIMES = {
    "noon": __import__("datetime").datetime(2026, 10, 6, 13, 0, tzinfo=catalogue.IST),
    "evening": __import__("datetime").datetime(2026, 10, 6, 20, 30, tzinfo=catalogue.IST),
    "morning": __import__("datetime").datetime(2026, 10, 6, 8, 30, tzinfo=catalogue.IST),
}


def load_golden(which: str = "dev") -> list[dict]:
    paths = {"dev": [GOLDEN], "heldout": [HELDOUT], "both": [GOLDEN, HELDOUT]}[which]
    return [json.loads(line) for path in paths for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _tokens(s: str) -> set[str]:
    return {t.rstrip("s") for t in re.findall(r"[a-z]+", s.lower())}


def check(expect: dict, req: FoodRequest | None) -> dict[str, bool]:
    """Field-by-field comparison; only the fields the case specifies are checked."""
    if req is None:
        return {k: False for k in expect}
    res = {}
    for field, want in expect.items():
        if field == "dishes":
            got = req.dishes
            if not want:
                ok = not got
            else:
                ok = len(got) <= len(want) and all(any(_tokens(w) <= _tokens(g) for g in got) for w in want)
        elif field == "exclude":
            ok = set(req.exclude) == set(want)
        elif field == "tags":
            ok = set(want) <= set(req.tags) and len(set(req.tags) - set(want)) <= 1
        elif field == "groups":
            ok = {(g.diet, g.count) for g in req.groups} == {(g["diet"], g["count"]) for g in want}
        else:
            ok = getattr(req, field) == want
        res[field] = ok
    return res


async def read(mode: str, text: str, client: GroqClient) -> FoodRequest | None:
    if mode == "rules":
        return interpret_rules(text)
    if mode == "llm":
        got = await client.interpret(text)
        return normalise_llm(got, text) if got else None
    req = await understand(text, llm=client)
    if mode == "full" and req.source == "rules" and req.has_target:
        # production also asks the LLM for a second opinion when the rules' reading finds nothing to sell
        recs = planner.recommend(req, *KORAMANGALA, now=TIMES["noon"], limit=1, current_slot=catalogue.current_slot(TIMES["noon"]))
        slot = catalogue.current_slot(TIMES["noon"])
        if not recs and not planner.diagnose(req, *KORAMANGALA, now=TIMES["noon"], current_slot=slot):
            better = await second_opinion(text, req, llm=client)
            if better and better.has_target:
                req = better
    return req


async def score(mode: str, golden: list[dict], client: GroqClient) -> dict:
    per_case, by_field, by_cat = {}, defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    for case in golden:
        req = await read(mode, case["text"], client)
        res = check(case["expect"], req)
        ok = all(res.values())
        per_case[case["id"]] = {"ok": ok, "fields": res, "got": req.describe() if req else None}
        for f, v in res.items():
            by_field[f][0] += v
            by_field[f][1] += 1
        for c in case["cats"]:
            by_cat[c][0] += ok
            by_cat[c][1] += 1
    passed = sum(c["ok"] for c in per_case.values())
    return {"mode": mode, "passed": passed, "total": len(golden), "cases": per_case,
            "fields": {k: tuple(v) for k, v in by_field.items()}, "cats": {k: tuple(v) for k, v in by_cat.items()}}


def grounding(golden: list[dict]) -> dict:
    """Run the planner for every order-like request at several places and times; count constraint violations."""
    runs = bad = answered = 0
    examples: list[str] = []
    for case in golden:
        req = interpret_rules(case["text"])
        if req.intent != "order":
            continue
        for point in (KORAMANGALA, WHITEFIELD):
            for label, now in TIMES.items():
                recs = planner.recommend(req, *point, now=now, limit=8, current_slot=catalogue.current_slot(now))
                v = violations(req, recs, now)
                runs += 1
                answered += bool(recs)
                bad += len(v)
                examples += [f"{case['id']} {label}: {x}" for x in v[:2]]
    return {"runs": runs, "violations": bad, "answered": answered, "examples": examples[:10]}


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:5.1f}%" if b else "  n/a"


def render(results: list[dict], ground: dict, golden: list[dict], title: str = "Concierge evaluation") -> str:
    out = [f"# {title}", "",
           f"{len(golden)} labelled requests (English, Kannada and Hinglish in Latin script, groups, allergies, vague and conversational phrasing). "
           "A case passes only if **every** labelled field is right. LLM results are replayed from `evals/cassette.json`.", ""]
    out += ["| Mode | Cases passed | Pass rate |", "|---|---|---|"]
    for r in results:
        out.append(f"| {r['mode']} | {r['passed']}/{r['total']} | {pct(r['passed'], r['total'])} |")
    out += ["", "## By category (pass rate)", "", "| Category | n | " + " | ".join(r["mode"] for r in results) + " |",
            "|---|---|" + "---|" * len(results)]
    cats = sorted(results[0]["cats"], key=lambda c: -results[0]["cats"][c][1])
    for c in cats:
        n = results[0]["cats"][c][1]
        out.append(f"| {c} | {n} | " + " | ".join(pct(*[r["cats"][c][0], r["cats"][c][1]]) for r in results) + " |")
    out += ["", "## Field accuracy", "", "| Field | n | " + " | ".join(r["mode"] for r in results) + " |", "|---|---|" + "---|" * len(results)]
    for f in sorted(results[0]["fields"], key=lambda f: -results[0]["fields"][f][1]):
        out.append(f"| {f} | {results[0]['fields'][f][1]} | " + " | ".join(pct(*r["fields"][f]) for r in results) + " |")
    out += ["", "## Grounding (the guardrail)", "",
            f"{ground['runs']} planner runs over every order-like request x 2 delivery points x 3 times of day: "
            f"**{ground['violations']} constraint violations** (diet, allergens, budget, hours, delivery radius, catalogue membership); "
            f"{ground['answered']} runs returned at least one option.", ""]
    if ground["examples"]:
        out += ["Violations:", *[f"- {e}" for e in ground["examples"]], ""]
    best = results[-1]
    fails = [(cid, c) for cid, c in best["cases"].items() if not c["ok"]]
    text = {c["id"]: c for c in golden}
    out += [f"## Remaining failures ({best['mode']} mode, {len(fails)})", ""]
    for cid, c in fails:
        bad = [f for f, v in c["fields"].items() if not v]
        out.append(f"- `{cid}` “{text[cid]['text']}” → got *{c['got']}*; wrong: {', '.join(bad)}")
    return "\n".join(out) + "\n"


async def main_async(modes: list[str], out: Path | None, which: str) -> int:
    catalogue.load()
    client = GroqClient(api_key="", cassette=Cassette(CASSETTE), replay_only=True)
    sections, violations_found = [], 0
    names = {"dev": [("dev", "Concierge evaluation: dev set")], "heldout": [("heldout", "Concierge evaluation: held-out set")],
             "both": [("dev", "Concierge evaluation: dev set"), ("heldout", "Concierge evaluation: held-out set")]}[which]
    for key, title in names:
        golden = load_golden(key)
        results = [await score(m, golden, client) for m in modes]
        ground = grounding(golden)
        violations_found += ground["violations"]
        sections.append(render(results, ground, golden, title))
    report = "\n".join(sections)
    print(report)
    if out:
        out.write_text(report, encoding="utf-8")
    return 1 if violations_found else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", nargs="+", default=["rules", "llm", "cascade", "full"])
    ap.add_argument("--set", dest="which", choices=["dev", "heldout", "both"], default="both")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    raise SystemExit(asyncio.run(main_async(args.modes, args.out, args.which)))


if __name__ == "__main__":
    main()
