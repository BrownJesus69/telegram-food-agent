# Concierge evaluation

116 labelled requests (English, Kannada and Hinglish in Latin script, groups, allergies, vague and conversational phrasing). A case passes only if **every** labelled field is right. LLM results are replayed from `evals/cassette.json`.

| Mode | Cases passed | Pass rate |
|---|---|---|
| rules | 98/116 |  84.5% |

## By category (pass rate)

| Category | n | rules |
|---|---|---|
| dish | 39 |  89.7% |
| slot | 29 |  86.2% |
| tags | 22 |  90.9% |
| budget | 19 |  73.7% |
| group | 19 |  73.7% |
| hard | 18 |  55.6% |
| english | 15 |  93.3% |
| kannada | 14 |  71.4% |
| hinglish | 14 |  71.4% |
| combine | 13 |  61.5% |
| mood | 12 | 100.0% |
| allergen | 11 |  81.8% |
| diet | 8 |  87.5% |
| sort | 7 | 100.0% |
| spice | 7 |  57.1% |
| quantity | 6 |  83.3% |
| intent | 6 |  66.7% |
| cuisine | 3 | 100.0% |

## Field accuracy

| Field | n | rules |
|---|---|---|
| dishes | 62 |  98.4% |
| slot | 33 |  90.9% |
| tags | 22 |  90.9% |
| budget | 19 |  84.2% |
| servings | 19 |  94.7% |
| language | 15 | 100.0% |
| combine | 11 |  72.7% |
| budget_scope | 11 |  72.7% |
| exclude | 11 |  81.8% |
| intent | 8 |  75.0% |
| diet | 8 | 100.0% |
| spice | 8 |  75.0% |
| sort | 7 | 100.0% |
| quantity | 6 |  83.3% |
| cuisine | 3 | 100.0% |
| groups | 3 | 100.0% |

## Grounding (the guardrail)

672 planner runs over every order-like request x 2 delivery points x 3 times of day: **0 constraint violations** (diet, allergens, budget, hours, delivery radius, catalogue membership); 498 runs returned at least one option.

## Remaining failures (rules mode, 18)

- `a07` “order 2 filter coffee” → got *filter coffee*; wrong: quantity
- `b09` “4 people lunch, 250 per person” → got *lunch · for 4*; wrong: budget, budget_scope
- `c08` “eggless cake” → got *eggless cake*; wrong: exclude
- `d06` “swalpa khara tindi” → got *tiffin · hot spice*; wrong: slot
- `d11` “benne dose mattu kaapi” → got *benne dosa mattu coffee*; wrong: combine
- `d12` “bisi bele bhath 100 olage” → got *bisi bele bhath · under ₹100 per item*; wrong: dishes
- `e05` “do samosa aur chai” → got *samosa chai · ×2*; wrong: combine
- `e08` “chai aur pakoda shaam ke liye” → got *chai pakoda shaam liye*; wrong: slot
- `e10` “teen log ke liye dinner, 900 mein” → got *log liye · dinner · ×3*; wrong: servings, budget, budget_scope
- `e11` “butter chicken aur naan” → got *butter chicken naan*; wrong: combine
- `j03` “show my cart” → got *cart*; wrong: intent
- `j06` “ok cool bye” → got *ok cool bye*; wrong: intent
- `k04` “date night dinner for two, nothing too spicy” → got *date night nothing too · dinner · hot spice · for 2*; wrong: spice
- `k05` “it's raining, want something hot and comforting” → got *s raining + comforting · hot spice*; wrong: tags
- `k08` “pandu hasivu, swalpa kharada tindi” → got *pandu kharada tiffin*; wrong: spice, slot
- `k09` “veg pizza without cheese” → got *pizza · veg*; wrong: exclude
- `k10` “birthday party for 10 kids, snacks under 3000 total” → got *birthday party total · snack · for 10 · under ₹3000 total*; wrong: tags
- `k15` “biryani with extra raita for 3, 100 each” → got *biryani + extra raita each · for 3*; wrong: budget, budget_scope
