# QA report: live run on Telegram Web (2026-10-07, 00:05–00:15 IST)

Method: the production container (`docker compose`, image built from commit `554ea85`) was driven through Telegram Web in
Chrome as a customer, using the Claude in Chrome extension. The bot was running the real Groq key, the delivery simulator
and the SQLite volume. The tester's Telegram account is also the admin account, so admin cards arrived in the same chat.
Orders are fictional; nothing real is ordered.

## What was exercised live and what happened
| Flow | Result |
|---|---|
| `/start` | Welcome text with examples, current meal slot ("latenight"), address prompt |
| Address book | Existing migrated address shown; *Add new address* → popular-area buttons → Indiranagar → label *Office* → saved and activated |
| `light dinner for 2 under 500, no onion garlic` | Understood as *dinner · light · for 2 · under ₹500 total · no onion-garlic*; one Jain-friendly option with reasons and kcal |
| Select → cart → typed landmark → confirm screen | Confirm screen showed delivery address, recipient, instructions and the *Change address / Change recipient* buttons |
| Confirm COD | Customer confirmation plus admin card with Accept/Reject arrived |
| Unattended lifecycle (simulator) | Accepted → Preparing (rider named) → Out for delivery → **live-location map** moving in the chat → "halfway" / "almost there" → Delivered with 1–5 ⭐ buttons |
| Admin card | Edited in place at each stage (rider added, buttons advanced) |
| Rating | 5⭐ stored; `/track` and `/stats` both reflected it |
| `feed 4 people, 2 veg and 2 non veg under 1500` | Several single-kitchen plans, each with both diets; *Add all to cart* filled a two-line cart in one tap |
| `ondu masala dose mattu filter kaapi` (Kannada, at midnight) | Read as *masala dosa + filter coffee*; no match, with reasons: one kitchen closed (opens 7 am), another 4.5 km away vs its 3.9 km range |
| `biryani under 100` | No match, with "cheapest match is ₹185 (Veg Dum Biryani, …)" |
| `/stats`, `where is my order` | Funnel, GMV, rating, AI counters; natural-language tracking with progress bar |
| Ops dashboard (second tab) | Renders KPIs, funnel, per-hour chart, recent orders, AI + eval panel, system health; refreshes every 5 s; no console errors |

## Defects found by this run, and fixed
1. **Unnecessary LLM call, mislabelled answer.** `biryani under 100` was shown as *(AI-assisted)* and echoed
   "biryani · Biryani". The budget already explained the miss, so the LLM second opinion was a wasted call. Fix: ask the LLM only
   when `diagnose()` finds no explaining constraint; drop a cuisine that merely repeats a dish. Regression tests added; re-verified
   live (answer is now rules-only and reads cleanly).
2. **Dashboard float formatting** ("last backup 2m 39.80000000000001s ago"). Fix: round in the formatter.
3. **Tooling, not product:** the older Telegram Web client (`/k/`) stopped refreshing mid-session (a message showed a pending clock
   although the bot had answered in 400 ms; confirmed in the container logs). Reloading the newer client (`/a/`) showed the correct
   state. Noted so nobody mistakes it for a bot failure.

## Not exercised live (covered by automated tests only)
Voice notes (needs a microphone), sharing a GPS pin (Delhi pin rejection and Bengaluru pins are tested in `tests/test_addresses.py`),
the friend/recipient flow, rate limiting, rejection by the simulated kitchen, and restart-resume mid-ride.

## Privacy note on the recording
The GIF captured during this run shows the tester's personal chat list, so it is **not** committed to the repository. The
screenshots in `docs/media/` are of the ops dashboard only.
