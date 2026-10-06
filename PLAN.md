# FoodBot — audit and 13-hour integration plan

Audit date: 2026-10-06. Everything under "Verified" was observed in this session (file reads, `pytest`, data profiling, HTTP fetches). Everything under "Assumed" was not checked.

## 1. Audit — what the project is today

Telegram long-polling bot (aiogram 3): share GPS location → regex parse (Groq LLM only as fallback) → fuzzy item search → single-restaurant cart → COD order → admin accept/reject/status buttons. SQLite, CSV catalogue, no Docker, no CI.

### Verified problems (ranked by impact on the employer's notes)

| # | Finding | Evidence |
|---|---|---|
| 1 | **Catalogue is real OSM restaurants with templated fake menus.** 4,037 real places × 5 template items = 20,185 items but only **50 distinct item names**. 2,251 restaurants got "Veg Meal / Chicken Meal / Paneer Starter / Soft Drink / Dessert Cup", which `services/search.py` explicitly filters out as "generic" — roughly 11k items can never be returned. Contradicts the "don't use real data" note. | `Data/menu.csv` profile; `GENERIC_ITEM_NAMES` in `services/search.py:13` |
| 2 | **Menu can't serve a Bangalore customer.** No idli-vada/set dosa/benne dosa/bisi bele bath/thatte idli/chaats/filter-coffee-and-snacks variety, no meal-time awareness, 84% of items are veg only because of the templates. | same profile |
| 3 | **One location per user, GPS-share only.** The profile location *is* the delivery address; `create_order` copies `users.latitude/longitude` at order time. No address book, no typed address, no "deliver to a friend", no change on the confirm screen. Search also uses that same single point, so ordering for home from the office means re-sharing GPS and losing the office location. | `handlers.py:229`, `db.py` schema, `orders.py:116` |
| 4 | **Test suite is red.** `test_order_flow_idempotent` fails with `KeyError: 'I001'` (item ids are now `M000001…`). Tests import root `search.py`; the live bot uses `services/search.py`. | `pytest -q`: 1 failed, 6 passed |
| 5 | **Two search engines, drifting.** Root `search.py` (rapidfuzz, used by `orders.py` for ETA and by tests) vs `services/search.py` (hand-rolled scorer, used by handlers). | `orders.py:5`, `handlers.py:18` |
| 6 | **Closed restaurants/inactive items are not filtered on the live path.** `services/search.py` checks `getattr(item, "active", 1)` / `in_stock` / `rest.active`, but the dataclasses have `available` / `is_open`, so the checks are no-ops. | `services/search.py:228-235` vs `catalogue.py` dataclasses |
| 7 | **Will break on Linux/Docker.** `DATA_DIR` defaults to `data`, the folder is `Data` (works on Windows only). `.env` uses `DATABASE_PATH`, `config.py` reads `DB_PATH`. | `config.py:13-14`, `.env` keys |
| 8 | **Repo hygiene.** Files named `gitignore` / `env.example` (no leading dot) so nothing is actually ignored; 4 `handlers.py.bak*`, `fix_project.py`, `fix_handlers_syntax.py`, `XYZ.py`, `Run.txt` (contains a path from another folder name), `.pyc` committed-looking files. Repo is named `whatsapp-food-agent` but the bot is Telegram. | directory listing |
| 9 | **Hosting.** The GitHub repo is **empty** (nothing pushed; also means no secret leaked — good). The Render URL returned **HTTP 503**. A polling bot has no HTTP port, so Render's free web service model doesn't fit it. | WebFetch results |
| 10 | **AI is a thin fallback.** Groq is only called when regex finds no results; no conversation, no tool use, no evals. | `handlers.py:290-297`, `parser.py` |

### Strengths worth keeping (steelman)
- Idempotent checkout (`confirmation_key` + `BEGIN IMMEDIATE`) and an explicit order state machine (`FLOW`) — genuinely good; keep and extend.
- Admin gating, callback validation, HTML escaping — keep.
- Keeping the LLM out of the money path is the right instinct; the plan below makes that a stated design principle.

### Assumed (not verified)
- Free-tier limits and model names for Groq / Gemini / Geoapify / Nominatim change; re-check at build time.
- `web.telegram.org` login in Chrome must be done by you (I will not enter credentials).

## 2. Design principle (the "senior engineer" story)

> **The LLM proposes; deterministic code disposes.** Every LLM output is schema-validated and resolved against the catalogue. The model can never invent an item, a price, an address or an order. Everything it can do is a tool call into tested code.

## 3. Feature set (what an end user would want)

**A. Generated Bangalore catalogue (replaces OSM data)** — ~40 real Bangalore neighbourhood centroids (coordinates are facts), ~250 *fictional* restaurants across archetypes (Darshini, Udupi, Military Hotel, Andhra mess, biryani, North Indian, Chinese, Kerala, Mangalorean seafood, chaat, rolls, pizza, burger, healthy bowls, bakery, cafe, juice, desserts, late-night, tiffin/home-meal), ~350-dish master list with price bands, **meal-slot tags** (breakfast/lunch/snack/dinner/late-night), diet tags (veg/egg/non-veg/Jain), spice level, allergens. Opening hours per archetype, so breakfast places are closed at 9 pm. Seeded RNG → deterministic; pydantic validation + coverage tests ("every locality has ≥N open options in every meal slot").

**B. Addresses and "order for someone else"** — address book (Home / Office / Friend / custom), switch the active address in one tap from the search results, cart, and confirm screens; add by sharing a pin, typing an address (geocoded, user confirms the match), or picking from a list; recipient name + phone per order; per-order address *snapshot* (editing the address book never mutates past orders); delivery-radius check per address with a clear message; reorder to a different address.

**C. AI Concierge (the unique part)**
1. Tool-calling agent: "light dinner for 2, no onion-garlic, under ₹500, deliver to office at 8 pm" → tools `search_menu`, `check_open`, `list_addresses`, `build_cart`. Understands Kannada/Hinglish ("ondu masala dose kodi").
2. Voice notes → speech-to-text → same agent.
3. Meal-time awareness: "good morning" at 8 am surfaces breakfast items open now.
4. Group/diet intents: "feed 4 people, 2 veg 2 non-veg".
5. **Eval harness**: ~100 golden queries scored in CI (parse accuracy, hallucinated-item rate = 0). This is what separates "used AI" from "engineered with AI".

**D. Wow demo** — simulated delivery: after the restaurant accepts, a courier "rides" the route; the bot edits a Telegram live-location message every few seconds and pushes status updates. Plus a restaurant simulator that auto-accepts after a random delay (admin buttons still work) so the demo runs hands-free.

**E. Enterprise-grade engineering** — `src/` package layout, pydantic-settings config, repository layer over SQLite (WAL), structured JSON logs + correlation ids, `/healthz` + metrics endpoint, ops dashboard (orders, funnel, AI latency/cost-free token counts), rate limiting, retries/timeouts/circuit-breaker on external APIs, ruff + mypy + pytest, GitHub Actions CI, Dockerfile + docker-compose (`restart: unless-stopped`, healthcheck), ADRs documenting trade-offs, README with architecture diagram.

**F. "Built with AI" evidence** — `CLAUDE.md`, `docs/AI_WORKFLOW.md` (what Claude generated, what you decided, what you rejected), prompt log, QA GIFs from the Chrome-extension test runs.

## 4. 13-hour schedule (zero spend)

| Phase | Hours | Output | Cut line |
|---|---|---|---|
| 0. Stabilise | 1.0 | Package layout, one search engine, green tests, dotfiles fixed, `git init` + first push, `CLAUDE.md` | must |
| 1. Generated catalogue | 2.0 | Generator + validator + tests, new `restaurants.csv`/`menu.csv` (old OSM scripts archived) | must |
| 2. Addresses / recipient | 2.5 | Address book, switch-anywhere UX, typed-address geocoding, snapshot on orders, tests | must |
| 3. AI concierge | 3.0 | Tool-calling agent, Kannada/Hinglish, meal-time awareness, evals in CI | must (voice = stretch) |
| 4. Delivery simulation | 1.0 | Live-location courier + restaurant auto-accept | should |
| 5. Ops + Docker + CI | 1.25 | compose, healthcheck, dashboard, metrics, Actions | must |
| 6. QA + demo polish | 1.0 | Telegram Web test run via Claude in Chrome, GIFs, README, demo script | must |
| Buffer | 1.25 | — | — |

Stretch if time remains: Telegram Mini App map for address pick, photo-of-food ordering, Postgres via compose, bill-splitting for group orders.

## 5. Costs and hosting (all free; verify limits at build time)
- LLM: Groq free tier (existing key) primary, Gemini free tier as fallback. Rate-limited — hence caching and the deterministic parser first.
- Geocoding: Geoapify free tier (existing key) or Nominatim (1 req/s, needs a User-Agent).
- 24/7: Docker on your own machine with `restart: unless-stopped`. Polling works behind NAT, so no tunnel is needed; the bot is offline whenever the machine is asleep. A truly always-on free host (e.g. an always-free cloud VM) is unverified here and usually needs a card for sign-up.
- Render: drop it for the polling bot; use it only if the bot is switched to webhooks with a health endpoint, and expect cold starts on the free plan.

## 6. Risks
- 13 h is tight for B + C + D + E; Phases 0-3, 5 and 6 are the core and 4 is the first to cut.
- Free LLM tiers can rate-limit mid-demo → the deterministic parser must stay the fallback and the demo script should avoid bursts.
- Generated restaurant names must not collide with real brands; the generator will use a banned-names list and the README will state data is synthetic.

---

## Progress log
- **2026-10-06 — Phase 0 + 1 done:** package layout, single search engine, green tests, generated catalogue (522 restaurants, 12,140 items).
- **2026-10-06 — Phase 2 done:** address book, switch-anywhere, order for someone else, order snapshots.
- **2026-10-06 — Phase 3 done:** AI concierge (rules + Groq cascade, grounded planner, groups/bundles/allergens, voice notes,
  explanations), 164-case eval harness with held-out set and grounding gate. Measured: held-out 87.5% (rules) → 91.7% (full
  pipeline); LLM-only 68.8%; 0 guardrail violations. See `evals/RESULTS.md` and ADR 0002.
- Next: Phase 4 (delivery simulation), Phase 5 (Docker, CI, dashboard), Phase 6 (QA via Chrome, demo script).
- **2026-10-06 — Phase 4 done:** delivery simulation (kitchen auto-accept/prepare, generated rider with live-location ride,
  milestone messages, `/track`, ratings, admin cards edited in place). Single `fulfilment.advance()` path for admin, customer
  and simulator; scheduler is stateless (restart-safe). 12 simulation tests incl. a mutation check.
- **2026-10-06 — Phase 5 done:** Docker image + compose (non-root, read-only, healthcheck, restart policy, volume), in-process ops server
  (/healthz, /metrics, protected dashboard), structured JSON logs with per-update context, per-user rate limiting, global error net,
  SQLite online backups, funnel analytics, `/stats`, graceful SIGTERM, CI workflow, pre-commit, ADR 0003. Bot now runs in the container.
