# ADR 0002: The LLM proposes, deterministic code disposes

Status: accepted (2026-10-06)

## Context
Customers type things like *"light dinner for 2 under 500, no onion garlic"*, *"ondu masala dose mattu kaapi"* or
*"kuch meetha, 100 ke andar"*. A food-ordering bot that handles this needs language understanding, but it also moves
money and promises food: an invented dish, a wrong price, an ignored allergy or a closed kitchen is a real failure.

Constraints: zero spend (Groq free tier: 8,000 tokens/min and 1,000 requests/day on the key in use, ~1,100 tokens
per interpretation), a model catalogue that changes under us (the originally configured model, `llama-3.1-8b-instant`,
now returns 404, which silently disabled the first version's LLM fallback), and a need for repeatable tests and CI.

## Decision
1. **Narrow interface.** Both interpreters produce one typed object, `FoodRequest` (`foodbot/concierge/intent.py`):
   enums, bounded integers and short vocabulary lists. `FoodRequest.clean()` coerces or drops anything outside the
   vocabulary. The LLM never sees the catalogue, never emits prices, ids or restaurant names, and its output is
   validated twice (provider-side strict JSON schema, then `clean()`).
2. **Deterministic planner.** `planner.recommend()` turns a `FoodRequest` into suggestions using only catalogue data.
   Hard constraints (open now, in stock, delivery radius, diet, allergens, budget, spice) are never relaxed; every
   "why this" reason shown to the customer is computed from catalogue fields.
3. **Cheap first.** Rules (English + Hinglish + Kannada vocabulary) handle every message first: free, instant, testable.
   The LLM is consulted only when the rules find nothing to search for, or when their reading returns no results
   (`understand.second_opinion`). The LLM reading is merged with the rules' reliable numbers (budget, head-count).
4. **Fail soft.** No key, 429, outage, schema failure or a removed model all degrade to the rules. A circuit breaker
   stops calling after repeated failures or a rate limit; a removed model falls through to the next candidate; one
   bad generation is retried once before it counts as a failure.
5. **Measure it.** `evals/` holds a 116-case dev set and a 48-case held-out set written after the rules were tuned.
   Results are recorded to a cassette so CI replays LLM behaviour offline and deterministically. A grounding check
   runs the planner at several places and times and fails the build on any violated hard constraint.
6. **Show the work.** Every answer starts with "I understood: ..." (flagged *AI-assisted* when the LLM was used) and
   each suggestion carries its reasons, so the customer can correct a misreading in one message.

## Alternatives considered
- *Free-form tool-calling agent* (LLM calls `search_menu`, `add_to_cart`, ...). More impressive in a demo, but 3-4 calls
  per message against an 8k tokens/minute budget, non-deterministic tests, and a larger surface for prompt injection.
  The typed-request design keeps the same capabilities (groups, bundles, allergens) with one optional call.
- *LLM-first with rules as fallback.* Better on odd phrasing, but spends the free quota on messages like "biryani under 300".
- *Embeddings for retrieval.* Unnecessary for a 590-dish vocabulary; fuzzy token matching with strict coverage is
  transparent and tested (it also fixed a bug where "biryani" fuzzily matched "Irani Chai").

## Consequences
- Prompt injection has nowhere to go: the worst a hostile message can do is produce an odd-but-valid `FoodRequest`
  (tested), which the planner answers from the catalogue like any other.
- "No onion/garlic" is honoured only for dishes tagged `jain` in the catalogue; the bot says so instead of guessing.
- Quality is a number we can watch (`python -m evals.run`) and gate in CI; changing the prompt means re-recording the
  cassette (`python -m evals.record`, ~25 minutes on the free tier).
- Known limits are documented in `evals/RESULTS.md` rather than hidden.

## Amendment (2026-10-07): red-teaming the boundary
The claim "the worst a hostile message can do is an odd-but-valid request" was only argued, not attacked. Probing it (property
tests, a 96-case red-team set, forged-callback tests; see [THREAT-MODEL](../THREAT-MODEL.md)) found that the boundary had three
holes, all fixed:

1. **The model could overrule what the customer stated.** `merge()` preferred the model's diet and budget, so "I'm vegetarian,
   surprise me" plus a reply of `diet: nonveg` served meat. Decision: *stated beats inferred.* A diet, budget, party size or group
   found by the rules is authoritative; the model fills blanks and may only *add* exclusions. Conflicting diet words in one
   message resolve to the safer reading.
2. **A model could put its own words in the bot's mouth.** Dish and restaurant strings are free text. Decision: every word that
   survives `normalise_llm` must be in the catalogue vocabulary or in the customer's own message.
3. **`clean()` was not total.** Arbitrary JSON (`diet: [null]`, `budget: Infinity`) raised; the caller's `try/except` hid it.
   Decision: `clean()` is total and idempotent over any JSON value, and a test generates hostile replies to keep it so.

Two consequences worth stating:
- The rules, not the model, are the safety-critical reader, so they are tested like one (held-out phrasings of allergies, diets and
  budgets; invisible and look-alike characters). The first held-out run failed 16 of 24 cases, which the dev set had hidden.
- Where the rules *cannot* enforce a stated need (halal, diabetic, an allergen outside the nine modelled), the bot says so rather than
  staying silent (`FoodRequest.cautions`). Honesty about a limit is cheaper than a guarantee we do not have.

## Amendment (2026-10-07): the production model is chosen by measurement
The first model (`openai/gpt-oss-20b`) was picked because it was the first free Groq model with strict JSON schemas. A bake-off on the same
cases ([evals/BAKEOFF.md](../../evals/BAKEOFF.md)) showed `qwen/qwen3.8-27b` reads held-out messages better alone (83% vs 67%) using about 40% of
the tokens per call (428 vs 1,128) in about half the time, and on its own free quota. Because of the boundary above, every model scores 0%
through the pipeline on the red-team set, so the switch is a cost, latency and recall decision, not a safety one. Changes: `config.DEFAULT_GROQ_MODEL`,
the recorded replies the evals replay are now the production model's (`evals/cassettes/qwen_qwen3.8-27b.json`), and the previous model stays
as a fallback after qwen (`llm.DEFAULT_MODELS`). Held-out accuracy of the full pipeline went from 91.7% to 93.8%.
