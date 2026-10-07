# Changelog

Format: [Keep a Changelog](https://keepachangelog.com), versions follow the roadmap in [PLAN.md](PLAN.md).

## [0.5.0] - 2026-10-07
### Changed
- **Production LLM is now `qwen/qwen3.8-27b`**, chosen by a measured bake-off (`evals/BAKEOFF.md`): 83% vs 67% held-out accuracy alone at about 40% of the tokens. Full-pipeline held-out accuracy 91.7% -> 93.8%.
### Added
- Reorder ("the usual", `/reorder`), split-the-bill, Telegram Mini App map picker and photo-of-food ordering (see the feature docs in `docs/`).
- Supply chain and quality gates in CI: CodeQL, Dependabot, Trivy image scan, GHCR publish on `main`, mypy, coverage gate (85%).
- `tools/loadtest.py` and [docs/LOADTEST.md](docs/LOADTEST.md): 50 simultaneous customers through the real dispatcher.
- Red-team suite (96 hostile or awkward messages, four readers incl. a fully compromised model), property-based tests (Hypothesis), forged-callback tests, threat model.
- Honest warnings when a stated need cannot be enforced (halal, diabetic, an unmodelled allergen).
### Fixed
- A model reply could overrule the customer's stated diet or budget; `clean()` crashed on hostile JSON; a model could put its own words in the bot's reply.
- Forged callback data could store negative or huge cart quantities and probe other customers' order numbers.
- Reader missed ordinary allergy phrasings (`can't eat eggs`, `wheat allergy`, `onion free`), read `I'm not vegetarian` as vegetarian, and ignored `1,000`, `2k`, zero-width and look-alike letters.
- Backups could overwrite each other within one clock tick (Windows).

## [0.4.1] - 2026-10-07
### Added
- Live QA report, demo script, dashboard screenshots; CI badge.
### Fixed
- LLM second opinion was spent (and mislabelled) when the budget already explained an empty result; dashboard float formatting.

## [0.4.0] - 2026-10-06
### Added
- Docker image and compose (non-root, read-only filesystem, healthcheck, restart policy), health/metrics/dashboard server, per-user rate limiting, global error net, SQLite backups, funnel analytics, GitHub Actions CI.
- Delivery simulation: kitchen auto-accept/prepare, generated riders with a live-location ride, `/track`, ratings.

## [0.3.0] - 2026-10-06
### Added
- AI concierge: rules reader + Groq cascade, grounded planner, group plans and bundles, allergens, voice notes, eval harness (dev + held-out), cassette replay.

## [0.2.0] - 2026-10-06
### Added
- Address book, switch address from anywhere, order for someone else, order snapshots.

## [0.1.0] - 2026-10-06
### Added
- Generated catalogue (522 kitchens, 12,140 items) replacing real data; stabilised the original bot (repo hygiene, tests).
