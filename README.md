# FoodBot — AI-built Telegram food ordering for Bengaluru

A Telegram bot where a customer shares a location, asks for food in plain language
("benne dosa", "3 chicken biryani under 300", "masale dose"), builds a cart, places a cash-on-delivery
order, and a restaurant operator accepts / prepares / dispatches it from the same chat.

**All restaurants, menus, prices, ratings and hours are synthetic.** Nothing comes from a real
restaurant. Neighbourhood coordinates are approximate area centres.

Status: **v0.2** — rebuilt around a generated catalogue. See [PLAN.md](PLAN.md) for the audit and the roadmap
(addresses & "order for someone else", AI concierge, delivery simulation, Docker/CI).

## What's in the catalogue
| | |
|---|---|
| Restaurants | ~520 fictional kitchens across 48 Bengaluru neighbourhoods |
| Menu items | ~12,000, from a master list of ~590 dishes |
| Kinds of place | 34 archetypes: Darshini, Udupi, Military Hotel, Andhra mess, Kerala, Coastal seafood, Chettinad, biryani, Punjabi, kebabs, Indo-Chinese, momos, chaat, shawarma, pizza, burgers, cafés, Irani cafés, chai stalls, bakeries, juice bars, desserts, sweet shops, healthy bowls, pan-Asian, grills, home-style, Gujarati, Bengali, late-night… |
| Meal awareness | every dish is tagged breakfast / lunch / snack / dinner / late-night; restaurants have real opening hours (some close after midnight) |
| Diet & allergens | veg / egg / non-veg, spice level 0-3, calories, indicative allergens, tags (jain, high-protein, bestseller…) |

The catalogue is **generated, not hand-edited**: `python -m tools.catalogue_gen.generate`
(seeded, deterministic). `python -m tools.catalogue_gen.validate` checks it, and a test fails if
`seed_data/` ever drifts from what the generator produces.

## Run it
```bash
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                      # fill in TELEGRAM_BOT_TOKEN and ADMIN_CHAT_ID at minimum
python -m pytest                                          # 30+ tests, no network needed
python -m foodbot
```
1. Open the bot in Telegram, press **Start**. The admin account (`ADMIN_CHAT_ID`) must also press Start once.
2. Share a location inside Bengaluru → "I want biryani under 300" → Select → Checkout → Skip → Confirm.
3. The admin chat receives the order with Accept / Reject buttons and walks it through the status flow.

Only one instance may poll a bot token at a time (Telegram returns a `Conflict` error otherwise).

## Layout
```
foodbot/            application package (python -m foodbot)
  handlers.py       Telegram conversation + callbacks
  orders.py         cart, idempotent checkout, order state machine
  parser.py         regex query parser, Groq LLM as fallback
  services/         catalogue (loader, open-hours logic), search, eta, distance
seed_data/          generated restaurants.csv + menu.csv (+ catalogue_meta.json)
tools/catalogue_gen/ dish master list, archetypes, localities, generator, validator
tools/archive/      the original OSM-based scripts and data, kept for reference
tests/              unit, data-quality and end-to-end conversation tests
```

## Design notes
- **Search is deterministic.** Hard filters (open now, in stock, inside the restaurant's delivery radius, budget, diet)
  are never relaxed silently; ranking blends relevance, rating, proximity, popularity and meal-slot fit.
- **The LLM never touches money or inventory.** It may only help interpret a request; everything it returns is
  resolved against the catalogue.
- **Checkout is idempotent** (confirmation key + `BEGIN IMMEDIATE`), orders follow an explicit state machine,
  and admin actions are gated by chat id.
- ETAs are catalogue estimates (kitchen prep + traffic-aware travel), not live tracking.

## Security
Never commit `.env` (it is git-ignored). Rotate any key that has appeared in a chat or screenshot.
