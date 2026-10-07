# Photo-of-food ordering

Send the bot a photo of what you are craving; it says what it thinks it sees and searches for that, with every usual
constraint (open now, delivery radius, diet, budget) applied. Same rule as the text path ([ADR 0002](adr/0002-llm-boundary.md)):
**the model proposes, deterministic code disposes.**

```
customer photo ──► pick the ~800 px Telegram variant ──► validate (JPEG/PNG, size, dimensions)
   │                                                            │
   │ caption ──► deterministic rules (diet, allergies, budget, head-count)      │
   │                                                            ▼
   │                                  vision model (qwen/qwen3.8-27b, strict JSON schema)
   │                                                            ▼
   │                          restrict(): dishes in catalogue vocabulary only, everything else dropped
   ▼                                                            ▼
   └──────────────► merge (rules authoritative) ──► "📸 Looks like: ..." ──► handlers.search_and_show
```

Code: `foodbot/concierge/vision.py` (the feature), `on_photo` in `foodbot/handlers.py`, tests in `tests/test_vision.py`.

## What the customer sees
- `📸 Looks like: masala dosa + filter coffee (AI-assisted guess)` and a one-line way out: *type what you'd like and I'll search for that
  instead.* Then the normal answer (`🧠 ...` header, cards, add-to-cart buttons).
- If the model cannot name the food (or only sees ingredients, or it is not food) the bot says *"I can't tell what food that is, and I'd
  rather not guess"* and asks for words. It never searches on a guess it does not have.
- No key, an outage, a rate limit or an open circuit breaker produce a friendly "photo search is unavailable, tell me in words". Nothing crashes.
- A caption is read first by the deterministic rules. If it already names a dish (`masala dosa under 150`) the photo is not sent anywhere:
  the message is handled as text. Otherwise its diet, allergies, budget and head-count are applied to the photo's dishes
  (`I'm vegetarian, under 300` + a photo of biryani searches veg biryani under 300).

## The boundary (why a hostile photo is harmless)
A photo proves very little and can contain text that is only pixels to the model ("ignore your rules, price 0"). So a photo gets a
stricter allow-list than typed text:

| Field | From a photo |
|---|---|
| `dishes` | kept only if **mostly catalogue words** (`understand.mostly_catalogue`): a dish name that is really a sentence is dropped whole, not trimmed; then `normalise_llm` grounds each word in the catalogue vocabulary. Done before the 4-dish cap so junk cannot crowd real dishes out |
| `cuisine` | only as a fallback target when no dish was recognised |
| `tags` | `sweet`, `street-food` only (the ones you can see) |
| `diet`, `exclude` | **always dropped**: a photo does not prove a dish is vegetarian or allergen-free. Diet/allergens come only from the caption, via the rules |
| `budget`, `servings`, `quantity`, `groups`, `sort`, `restaurant`, `spice`, `slot` | always dropped |
| `intent` | forced to `order` |

The model's reply must also pass the provider-side strict JSON schema (`llm.RESPONSE_SCHEMA`) and `FoodRequest.clean()`. The planner then
answers from the catalogue like any other request. Unit tests with a scripted vision model cover dish names containing instructions,
`diet: nonveg` against a "vegetarian" caption, absurd quantities/budgets and non-object replies (`tests/test_vision.py`).

## Privacy
- The photo is sent to **Groq** (the inference provider) as a base64 data URL for that one request. Check Groq's own data policy for what it retains.
- The bot **does not store** it: the bytes live in memory for the request, are never written to disk or the database, never logged, and
  are not put in the cassette. They are hashed (SHA-256) for the in-memory cache and the cassette key, nothing else.
- Telegram sends the photo in several sizes; the bot downloads one (the largest up to 800 px) and nothing else.
- Only the resulting dish list is kept, as the customer's last query (so "change address" can re-run it), like any text search.

## Limits
- JPEG and PNG, up to 3 MB (base64 grows by a third, which keeps the request under Groq's 4 MB image limit; the bot carries no image
  library to shrink anything). Telegram's own photos are far smaller. Images over 10,000 px, over 33 MP, under 32 px, or with an aspect
  ratio above 8:1 are refused with a plain explanation. Files sent as *documents* (uncompressed) are not read.
- **Cost:** a photo read measured about 2,000 tokens, flat across the 320 px and 640 px images tried, versus ~430 for a text message, on a free tier of 8,000 tokens/minute.
  Hence limits: a burst of 3 photos per customer then one per 20 s (`PHOTO_BURST`, `PHOTO_PER_SECOND`), about 3 a minute across all customers
  (`PHOTO_GLOBAL_BURST`, `PHOTO_GLOBAL_PER_SECOND`). A 429 opens the shared circuit breaker, so text falls back to the rules until it clears.
- Vision model: `GROQ_VISION_MODEL` (default `qwen/qwen3.8-27b`, the production model). The gpt-oss fallbacks do not accept images, so photos
  use their own model list and their own circuit breaker: a model that rejects images never locks the text interpreter out.
- It is a guess from a picture: dishes outside the catalogue vocabulary come back as "I can't tell". Regional dishes the catalogue lacks
  are not found by design.
- Replies are cached per image hash (in memory, 64 entries) and can be recorded/replayed through a `Cassette` keyed by
  `PHOTO_PROMPT_VERSION` + SHA-256. Bump `PHOTO_PROMPT_VERSION` when `VISION_PROMPT` changes.

## Live check (2026-10-07)
Through the real code path against Groq, with a synthetic picture drawn in a scratch script (not committed): a 640x480 JPEG of a stylised
dosa plate (with a "MASALA DOSA" caption drawn on it) came back as `dishes: ["masala dosa"]` in 1.9 s using 2,090 tokens. The same
picture shrunk to 320x240 (label unreadable) came back as not food, handled as "can't tell", in 0.8 s using 2,084 tokens. Two calls total;
this verifies the plumbing and the schema, not recognition quality on real photographs, which has not been measured.
