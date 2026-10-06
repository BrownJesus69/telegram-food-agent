# Demo script (about 6 minutes)

**One-line pitch:** a Telegram food-ordering agent for Bengaluru where an LLM is allowed to *understand* but never to *decide*,
built end to end with AI tools, measured with its own evaluation suite, and operated like a small production service.

## Before you start (2 minutes)
1. `docker compose up -d --build` and wait until `docker ps` says *healthy*.
2. Open `http://127.0.0.1:8080/dashboard?key=<DASHBOARD_KEY from .env>` in a second window.
3. In Telegram open the bot, send `/start`. If you are demoing from outside Bengaluru, use *Add new address* → a popular area.

## The walk-through
| Min | You say / do | What it shows | Employer note it answers |
|---|---|---|---|
| 0:00 | "Everything you'll see is synthetic: 522 generated kitchens, 12,140 menu items." Send `/start`. | Generated data, no real restaurants | *Don't stick to real data* |
| 0:30 | Send `light dinner for 2 under 500, no onion garlic` | "I understood: …" line, reasons per card, Jain-tagged dishes | *Use AI*, *critical thinking* |
| 1:15 | Tap **📍 Change address** → *Add new address* → pick an area → label **A friend / family** → name + phone | Home / office / friend addresses, recipient per order | *Edit location, order for someone else* |
| 2:00 | Send `feed 4 people, 2 veg and 2 non veg under 1500`, tap **Add all to cart** | One kitchen that serves both diets, one tap to a full cart | *Something unique* |
| 2:45 | Checkout → landmark → **Confirm**. Watch: accepted → preparing → rider live location moving → delivered → rate ⭐ | Simulated kitchen and rider, Telegram live location, admin card editing itself | *Something unique*, *enterprise grade* |
| 4:00 | Send `ondu masala dose mattu filter kaapi` (or `kuch meetha chahiye`) | Kannada / Hinglish, meal-time awareness, a *reasoned* "no match" (closed / too far) | *Anyone from Bangalore* |
| 4:30 | Send `/stats`, switch to the dashboard | Funnel, orders per hour, AI panel with eval scores, health checks | *Production grade* |
| 5:15 | Open `evals/RESULTS.md` or the README table | rules 87.5% → full pipeline 91.7% on unseen requests; LLM alone 66.7%; **0 guardrail violations** | *Thought process* |
| 5:45 | Show `docker compose ps` (healthy) and the green CI run on GitHub | Restart policy, healthcheck, CI that runs the same evals | *Enterprise grade* |

## Talking points worth saying out loud
- **The boundary:** the LLM only fills a typed `FoodRequest`; plain code applies open-now, radius, diet, allergens and budget.
  A hostile message can at worst produce an odd-but-valid request ([ADR 0002](adr/0002-llm-boundary.md)).
- **Honesty in measurement:** the rules were tuned on a dev set (99%); the held-out set I wrote afterwards says 87.5%. The LLM alone
  scores worse than the rules, which is why it is a backstop. I show the failures, not just the score.
- **Who did what (say it plainly):** Claude Code proposed and implemented the architecture and code under my goals and constraints (free tier only, 13 hours, the employer's notes), and I reviewed and approved the plan phase by phase. Be ready to explain each trade-off in your own words: the cheap-first cascade, the guardrail boundary, the stateless simulation, held-out evals, and keeping a QA GIF out of the repo because it showed a personal chat list.
- **Bugs found by testing, not luck:** a dead default model silently disabling the v1 fallback; "biryani" matching "Irani Chai";
  a Prometheus label-escaping bug; an unnecessary LLM call found in this very QA run ([QA report](QA-REPORT.md)).

## Questions to expect, honest answers
- *Is this deployed?* Docker on a laptop with auto-restart; 24/7 only while the machine is on. The same compose file would run on a free VM (not verified).
- *Why SQLite?* One writer, WAL, online backups; Postgres is a contained swap ([ADR 0003](adr/0003-operations-and-hosting.md)).
- *Why not a tool-calling agent?* Token budget (8k/min free tier), determinism and testability; the typed-request design keeps the capabilities with one optional call.
- *What would you do next?* Re-record the eval cassette with a sharper prompt (LLM-only is the weak spot), a Telegram Mini App map for address picking, photo-of-food ordering.
