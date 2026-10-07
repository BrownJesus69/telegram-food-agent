# Concierge evaluation: dev set

116 labelled requests (English, Kannada and Hinglish in Latin script, groups, allergies, vague and conversational phrasing). A case passes only if **every** labelled field is right. LLM results are replayed from `evals/cassettes/` (the production model's recorded replies).

| Mode | Cases passed | Pass rate |
|---|---|---|
| rules | 115/116 |  99.1% |
| llm | 97/116 |  83.6% |
| cascade | 115/116 |  99.1% |
| full | 114/116 |  98.3% |

## By category (pass rate)

| Category | n | rules | llm | cascade | full |
|---|---|---|---|---|---|
| dish | 39 | 100.0% |  87.2% | 100.0% | 100.0% |
| slot | 29 | 100.0% |  79.3% | 100.0% |  96.6% |
| tags | 22 | 100.0% |  77.3% | 100.0% | 100.0% |
| budget | 19 | 100.0% |  84.2% | 100.0% | 100.0% |
| group | 19 | 100.0% |  78.9% | 100.0% | 100.0% |
| hard | 18 |  94.4% |  61.1% |  94.4% |  94.4% |
| english | 15 | 100.0% | 100.0% | 100.0% | 100.0% |
| kannada | 14 |  92.9% |  64.3% |  92.9% |  85.7% |
| hinglish | 14 | 100.0% |  92.9% | 100.0% | 100.0% |
| combine | 13 | 100.0% |  76.9% | 100.0% | 100.0% |
| mood | 12 | 100.0% |  91.7% | 100.0% | 100.0% |
| allergen | 11 | 100.0% |  72.7% | 100.0% | 100.0% |
| diet | 8 | 100.0% |  87.5% | 100.0% | 100.0% |
| sort | 7 | 100.0% | 100.0% | 100.0% | 100.0% |
| spice | 7 |  85.7% |  57.1% |  85.7% |  71.4% |
| quantity | 6 | 100.0% |  83.3% | 100.0% | 100.0% |
| intent | 6 | 100.0% |  66.7% | 100.0% | 100.0% |
| cuisine | 3 | 100.0% | 100.0% | 100.0% | 100.0% |

## Field accuracy

| Field | n | rules | llm | cascade | full |
|---|---|---|---|---|---|
| dishes | 62 | 100.0% |  95.2% | 100.0% | 100.0% |
| slot | 33 | 100.0% |  84.8% | 100.0% | 100.0% |
| tags | 22 | 100.0% |  86.4% | 100.0% | 100.0% |
| budget | 19 | 100.0% | 100.0% | 100.0% | 100.0% |
| servings | 19 | 100.0% |  94.7% | 100.0% | 100.0% |
| language | 15 | 100.0% | 100.0% | 100.0% | 100.0% |
| combine | 11 | 100.0% | 100.0% | 100.0% | 100.0% |
| budget_scope | 11 | 100.0% |  90.9% | 100.0% | 100.0% |
| exclude | 11 | 100.0% |  72.7% | 100.0% | 100.0% |
| intent | 8 | 100.0% |  75.0% | 100.0% | 100.0% |
| diet | 8 | 100.0% | 100.0% | 100.0% | 100.0% |
| spice | 8 |  87.5% |  75.0% |  87.5% |  75.0% |
| sort | 7 | 100.0% | 100.0% | 100.0% | 100.0% |
| quantity | 6 | 100.0% | 100.0% | 100.0% | 100.0% |
| cuisine | 3 | 100.0% | 100.0% | 100.0% | 100.0% |
| groups | 3 | 100.0% | 100.0% | 100.0% | 100.0% |

## Grounding (the guardrail)

660 planner runs over every order-like request x 2 delivery points x 3 times of day: **0 constraint violations** (diet, allergens, budget, hours, delivery radius, catalogue membership); 564 runs returned at least one option.

## Remaining failures (full mode, 2)

- `d06` “swalpa khara tindi” → got *breakfast · sweet · medium spice*; wrong: spice
- `k08` “pandu hasivu, swalpa kharada tindi” → got *tiffin · breakfast · mild spice · under ₹100 per item*; wrong: spice

# Concierge evaluation: held-out set

48 labelled requests (English, Kannada and Hinglish in Latin script, groups, allergies, vague and conversational phrasing). A case passes only if **every** labelled field is right. LLM results are replayed from `evals/cassettes/` (the production model's recorded replies).

| Mode | Cases passed | Pass rate |
|---|---|---|
| rules | 42/48 |  87.5% |
| llm | 40/48 |  83.3% |
| cascade | 43/48 |  89.6% |
| full | 45/48 |  93.8% |

## By category (pass rate)

| Category | n | rules | llm | cascade | full |
|---|---|---|---|---|---|
| dish | 19 |  94.7% |  89.5% |  94.7% |  94.7% |
| english | 18 |  94.4% |  88.9% |  94.4% | 100.0% |
| slot | 13 | 100.0% |  53.8% | 100.0% | 100.0% |
| diet | 10 |  80.0% |  70.0% |  80.0% |  80.0% |
| group | 10 |  90.0% |  70.0% |  90.0% | 100.0% |
| budget | 9 | 100.0% |  66.7% | 100.0% | 100.0% |
| tags | 8 |  87.5% |  75.0% |  87.5% | 100.0% |
| combine | 6 |  83.3% | 100.0% |  83.3% |  83.3% |
| hard | 6 |  16.7% |  83.3% |  16.7% |  50.0% |
| kannada | 6 | 100.0% | 100.0% | 100.0% | 100.0% |
| hinglish | 6 |  83.3% |  66.7% |  83.3% |  83.3% |
| sort | 5 |  80.0% |  80.0% | 100.0% | 100.0% |
| quantity | 4 | 100.0% | 100.0% | 100.0% | 100.0% |
| allergen | 4 |  50.0% |  75.0% |  50.0% |  75.0% |
| spice | 4 | 100.0% |  75.0% | 100.0% | 100.0% |
| intent | 4 |  75.0% |  75.0% |  75.0% |  75.0% |
| cuisine | 2 | 100.0% | 100.0% | 100.0% | 100.0% |
| mood | 2 |  50.0% | 100.0% |  50.0% | 100.0% |

## Field accuracy

| Field | n | rules | llm | cascade | full |
|---|---|---|---|---|---|
| dishes | 26 |  96.2% | 100.0% |  96.2% | 100.0% |
| slot | 13 | 100.0% |  61.5% | 100.0% | 100.0% |
| diet | 10 |  90.0% | 100.0% |  90.0% |  90.0% |
| servings | 10 | 100.0% | 100.0% | 100.0% | 100.0% |
| budget | 9 | 100.0% | 100.0% | 100.0% | 100.0% |
| tags | 8 | 100.0% |  87.5% | 100.0% | 100.0% |
| combine | 6 | 100.0% | 100.0% | 100.0% | 100.0% |
| quantity | 5 | 100.0% | 100.0% | 100.0% | 100.0% |
| sort | 5 |  80.0% | 100.0% | 100.0% | 100.0% |
| budget_scope | 4 | 100.0% | 100.0% | 100.0% | 100.0% |
| exclude | 4 |  50.0% |  75.0% |  50.0% |  75.0% |
| spice | 4 | 100.0% |  75.0% | 100.0% | 100.0% |
| intent | 4 |  75.0% |  75.0% |  75.0% |  75.0% |
| cuisine | 2 | 100.0% | 100.0% | 100.0% | 100.0% |
| language | 2 | 100.0% | 100.0% | 100.0% | 100.0% |
| groups | 1 | 100.0% | 100.0% | 100.0% | 100.0% |

## Grounding (the guardrail)

270 planner runs over every order-like request x 2 delivery points x 3 times of day: **0 constraint violations** (diet, allergens, budget, hours, delivery radius, catalogue membership); 185 runs returned at least one option.

## Remaining failures (full mode, 3)

- `t30` “mujhe veg pizza chahiye bina cheese ke” → got *pizza · veg · bestseller · no onion-garlic*; wrong: exclude
- `t35` “what's in my basket” → got *basket*; wrong: intent
- `t45` “veggie burger and fries” → got *veggie burger + fries*; wrong: diet
