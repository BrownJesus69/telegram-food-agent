# FoodBot — working notes for Claude

Telegram food-ordering bot for Bengaluru; catalogue is **synthetic**. Goal of the repo: show production-grade,
AI-assisted engineering (see PLAN.md for the roadmap and the reasoning behind it).

## Commands
- Tests: `.venv/Scripts/python.exe -m pytest` (no network, frozen clock; must stay green)
- Lint: `.venv/Scripts/python.exe -m ruff check .`
- Regenerate data: `python -m tools.catalogue_gen.generate` then `python -m tools.catalogue_gen.validate`
- Run bot: `python -m foodbot` (only ONE instance per bot token)

## Rules
- Never print, log or commit values from `.env`. Redact tokens in any command output.
- `seed_data/*.csv` are generated: change the generator, never the CSVs; `test_committed_catalogue_matches_generator` enforces it.
- The LLM proposes, deterministic code disposes: anything an LLM returns must be validated and resolved against the
  catalogue before it can affect a cart, price, address or order.
- Open/closed logic goes through `Restaurant.open_at(now)`; tests freeze time via `catalogue.now_ist` (see tests/conftest.py).
- Keep zero-cost: free tiers only (Groq, Geoapify, Nominatim), no paid services.
- Windows host: a stray empty `Data/` folder may exist (a process held a handle on it); the real data dir is `seed_data/`.
