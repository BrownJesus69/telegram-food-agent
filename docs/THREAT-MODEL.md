# Threat model

A short, honest map of what could go wrong, what stops it, and what is still open. Every control below names the test that
checks it; every "open" item is something the tests do **not** cover.

## What is being protected

| Asset | Why it matters |
|---|---|
| The customer's **stated constraints** (allergens, diet, budget) | A wrong dish can hurt someone. This is the one failure that is not just an annoyance |
| **Order integrity**: prices, quantities, totals | Prices must come from the catalogue, never from a message or a model |
| **Other customers' data** (orders, addresses, phone numbers) | Privacy |
| **Operator actions** (accept, reject, deliver) | Only the configured admin may change an order's state |
| Secrets (`.env`: Telegram token, Groq key, dashboard key) | Account takeover, quota theft |
| Availability and the free-tier LLM quota | A flood of messages should not exhaust either |

## Who might do what

| Actor | Realistic attack | Note |
|---|---|---|
| A customer typing text | Prompt injection ("ignore your rules"), odd or obfuscated phrasing | Mostly harms only themselves: they are also the victim. The risk is the *model* misreading a legitimate constraint, not the customer attacking |
| A customer with a modified client | **Forged callback data** (negative quantities, other people's order ids, admin buttons) | Telegram clients never send these; an MTProto library can |
| Text from a third party | A forwarded message or a voice note that contains instructions | Treated exactly like typed text |
| The model itself | Hallucinates a diet, drops an allergy, or (if compromised) obeys an injection | The design assumes the model is *untrusted* |
| The operator | Leaks a key, runs two pollers | See "Secrets" and "Operations" |

## The trust boundary that matters most

```
customer text ──► rules (deterministic, authoritative for what was *stated*) ──┐
                                                                               ├─► FoodRequest ─► planner ─► cart ─► confirm tap
customer text ──► model (untrusted JSON, may fill blanks, may add exclusions) ─┘     (typed, bounded)  (reads the catalogue)
```

The model never sees a tool, a database, a price or another customer's data, and its output is a typed `FoodRequest`
(see [ADR 0002](adr/0002-llm-boundary.md)). Nothing it says reaches the cart, a price or an order except through the
planner, which reads the catalogue, and a customer's explicit confirm tap.

## Controls and the evidence for each

| Control | Where | Checked by |
|---|---|---|
| Every model field is an enum, a bounded number or a short list; unknown keys dropped; `clean()` is total and idempotent over arbitrary JSON | `intent.FoodRequest.clean` | `tests/test_properties.py` (Hypothesis, hostile replies incl. `NaN`, `Infinity`, nested junk, `__proto__`) |
| **What the customer stated cannot be overruled by the model**: rules-found diet, budget, party size and groups win; exclusions are a union (an allergy is never dropped); conflicting diet words resolve to the safer reading | `understand.merge`, `rules` diet block | `test_a_model_can_never_overrule_what_the_customer_stated`; red-team *worst-case model* column |
| A model cannot put its own sentences into the bot's reply: every surviving dish or restaurant word must be in the catalogue vocabulary or in the customer's message | `understand.normalise_llm` / `ground` | `tests/test_redteam.py::test_a_model_cannot_put_its_own_words_in_the_bots_mouth` |
| The planner never relaxes a hard constraint (open now, stock, radius, diet, allergens, budget) | `concierge/planner.py` | `tests/test_properties.py` (random requests at random places and times, mutation-checked: disabling the allergen, budget or spice filter makes it fail) and `evals/run.py` (0 violations in 930 runs) |
| Prices and totals come only from the catalogue; quantities are 1-10 whatever the callback says; unknown or unavailable items are refused | `orders.clamp_qty`, `orders.add_item`, `handlers._parse_pick` | `tests/test_abuse.py` |
| Callback data is untrusted: malformed data changes nothing and does not wedge the bot | handlers | `tests/test_abuse.py` (31 garbage callbacks) |
| A customer can only read, cancel, rate or confirm their own orders; admin buttons need an admin id | `orders`, `handlers.is_admin` | `tests/test_abuse.py` |
| Everything echoed back is HTML-escaped (landmarks, names, dishes) | `html.escape` at every render | `tests/test_abuse.py` (hostile landmark and 14 hostile messages; the test bot rejects any invalid Telegram HTML) |
| A stated need that has **no filter** (halal, diabetic, "no mushrooms", an allergen we do not model) is *flagged to the customer* instead of silently ignored | `rules.cautions`, `handlers.caution_line` | `evals/redteam.jsonl` (unenforceable and no-false-alarm categories) |
| A **photo** is untrusted input twice over (pixels the model reads, and a model that may be wrong): text inside an image is just pixels; diet, allergens, budget, servings and sort are *always* dropped from a vision reading, dish words must be catalogue words, and the caption is read by the rules first | `concierge/vision.py`, `handlers.on_photo` | `tests/test_vision.py` (hostile scripted replies, 45 tests) |
| A **Mini App payload** (`web_app_data`) is untrusted client data: size-limited, strict JSON object, finite numbers inside the Bengaluru box, then the same path as a shared pin; garbage changes no state | `address_flow.parse_miniapp_pin` | `tests/test_miniapp.py` (28 hostile payloads) |
| **Reorder and split** callbacks are strict-parsed and scoped to the order's own customer; a reorder is rebuilt from the *current* catalogue (never the old prices) | `orders.reorder_plan`, `billing`, `handlers` | `tests/test_reorder.py`, `tests/test_billing.py` |
| Rate limiting per user, global error net, secrets never logged, container is non-root with a read-only filesystem | `observability`, `docker-compose.yml` | `tests/test_ops.py`, CI docker job |

## Measured: how dangerous is "just use the LLM"?

[`evals/REDTEAM.md`](../evals/REDTEAM.md) runs 96 hostile or awkward messages through four readers. The model alone, replaying
its real recorded replies, drops or overrides a stated diet, allergen or budget on a large share of the dev cases; the full
pipeline does not drop any, **including when the model is replaced by one that obeys every injection and is asked on every
message**. What each set scored on its *first* run, before any fix, is in
[`evals/history/redteam-first-runs.md`](../evals/history/redteam-first-runs.md).

## Open / not covered

- **Unenforceable constraints are warned about, not enforced.** Halal, diabetic, "no pork", an allergen outside the nine we model: the bot says
  it cannot filter for them. A real service would need catalogue columns and kitchen attestations.
- **Constraints written only in Kannada or Hindi script** can be read by the model alone (the rules read Latin letters). The model is
  always consulted for such messages, and its exclusions are added, but a fully compromised model could drop them. The red-team
  *worst-case* column therefore excludes the three script cases; the real-reply column includes them.
- **The rules read English, Hinglish and romanised Kannada.** Other languages and heavy misspellings fall through to the model.
- **Allergen partially recognised.** "allergic to peanuts and kiwi" enforces peanuts; kiwi is not flagged.
- **A free-text echo channel remains**: up to 4 dish names of 60 characters, escaped and restricted to catalogue or customer words.
- **Intent flips** (a model labelling a message `cart` or `address`) only show the sender's own data; they are not scored as attacks.
- **No Telegram-side authentication beyond the user id.** The admin is whoever holds the configured id.
- **The dashboard key** protects a read-only page; it was printed once into a chat transcript during development, so rotate it before sharing.
- **Test scope:** these are unit-level, offline tests and recorded replies. Nothing here tests the live Groq model's behaviour today
  (it can change); re-record with `python -m evals.redteam --record` to refresh.
