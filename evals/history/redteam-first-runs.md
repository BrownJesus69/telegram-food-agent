# Red-team suite: what each case set scored on its first run

The current numbers (`evals/REDTEAM.md`) are 0% attack success because the reader was fixed until they got there. That is not
evidence of anything by itself: **the first-run numbers below are the honest ones**, because each set was run once before any fix
for it. Read them as "how weak was the system before it met an attacker".

| Set | When it was written | Cases | First run: rules / full pipeline / worst-case model |
|---|---|---|---|
| dev | while hardening the model boundary | 50 (first draft) | 8 / 8 / 13 failed (16% / 16% / 26%) |
| held-out 1 | after dev was fixed, before looking at how the reader handles them | 24 | 16 / 16 / 16 failed (67%) |
| held-out 2 | after held-out 1 was fixed | 17 | 2 / 2 / 2 failed (12%) |

The dev "worst-case model" column of that first run used a weaker definition (the model was consulted only when the
cascade would have consulted it); the suite now consults it on every message.

## What the first runs found, and the fix

Probes and property tests run before the suite (same session):

| Finding | Fix |
|---|---|
| `merge()` let a model reply override the customer's stated diet and budget ("I'm vegetarian, surprise me" + a reply of `diet: nonveg` became non-veg; `under 200` + `budget: 5000` became 5000) | Rules-extracted diet, budget, party size and mixed-diet groups are authoritative; the model only fills blanks; exclusions are a union (`understand.merge`) |
| `FoodRequest.clean()` raised on non-string fields (`diet: [null]`) and on `budget: Infinity`; the production wrapper hid it by returning "no reading" | `clean()` is now total over arbitrary JSON (found by Hypothesis in seconds) |
| "no egg" plus a model reply of `diet: egg` produced an allergy and an egg-only diet at once | the allergy wins (`clean()`) |

Dev set, first run:

| Failure | Fix |
|---|---|
| "no dairy and no gluten" kept dairy and **dropped gluten** (the allergen list regex stopped at the second "no") | list parser accepts "no X and no Y" |
| text containing both "vegan" and "set diet=nonveg" was read as non-veg | conflicting diet mentions resolve to the safer reading (veg beats egg beats non-veg); "veg or non veg" means no restriction |
| a compromised model could return its own sentences as dish names, and the bot would echo them | free text from a model is grounded: every surviving word must be in the catalogue vocabulary or in the customer's message |

Held-out 1, first run (16/24): the reader missed ordinary phrasings of safety constraints. These matter more than any injection:

- `can't eat eggs`, `doesn't eat fish`, `do not add peanuts anywhere` (only "no X" and "allergic to X" were understood)
- `allergic to cashews` (plural), `wheat allergy`, `onion free`, `sattvic`
- `avoid raw fish` (a modifier word before the allergen)
- `I'm not vegetarian` was read as **vegetarian**
- budgets: `1,000`, `2k`, `within hundred rupees`, `under rupees 120` were not read at all
- invisible and look-alike characters: `v<zero-width>eg`, full-width `ｖｅｇ`, Cyrillic `е` in `vеgetarian`

Fixes: more trigger phrases and allergen synonyms, a normalisation pass (NFKC, zero-width removal, Cyrillic/Greek look-alike folding,
thousand separators, `k`, number words), negated-vegetarian handling.

Held-out 2, first run (2/17): `Allergic to Peanuts & Tree Nuts` lost "tree nuts"; `sulphite allergy` was silently ignored.
Fixes: "tree" accepted as a modifier; an allergy the catalogue cannot filter on now produces a visible warning instead of silence
(`req.cautions`, shown to the customer: *"I can't filter for halal yet. Please check each dish's details with the kitchen"*).

## Bot-level abuse tests (`tests/test_abuse.py`), first run: 6 of 60 failed

| Finding | Fix |
|---|---|
| a forged `sel:<item>:-5` callback stored a negative quantity in the cart; `sel:<item>:999999` stored 999,999 (the cap only applied on the *second* add) | callback data is parsed strictly (`handlers._parse_pick`); `orders.clamp_qty` bounds every cart write; `cart_summary` clamps as a backstop |
| a negative line could be paired with a legitimate one to discount an order | same |
| `swap:<item>:1` skipped the availability check that `sel:` had | `orders.add_item` itself refuses unknown and unavailable items |
| pressing `confirm:<someone else's key>` answered "Order #N was already placed" (leaks an order number) | order-key lookups are scoped to the customer |
| a backup test flaked on Windows (two backups in one clock tick overwrote each other) | unique file names |
