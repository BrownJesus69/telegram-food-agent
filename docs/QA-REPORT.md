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

---

# Round 2: live run on Telegram Web (2026-10-07, 03:10-03:20 IST)
Same method as above (production container, real Telegram Web, Claude in Chrome), run after the red-team hardening.

| Flow | Result |
|---|---|
| `halal chicken biryani for 2` | No match (kitchens closed / out of range, with reasons) **plus** the new honesty line: *"I can't filter for halal yet. Please check each dish's details with the kitchen before ordering."* |
| Typed address `Embassy Tech Village, Bellandur` | Geocoder returned 4 candidates; picked one (Manyata Tech Park) |
| Label *A friend / family* → recipient name `Ravi <b>K</b> & Co` → phone | Saved as **Friend**; the name was sanitised to `Ravi bKb Co` (markup characters stripped), phone stored as +919876543210 |
| `late night snack under 300` with the friend's address active | Header shows the friend address; two late-night options with reasons |
| Cart: 1 × Egg Maggi (₹75) | Minimum-order warning (₹99) shown; `+` cleared it |
| Landmark `Gate 2 <a href="http://evil.example">click</a> & call Ravi` | Shown as literal text on the confirm screen, in the admin card and in the order record; never rendered as a link by the bot |
| Confirm COD, admin card | Admin card shows *Deliver to: Ravi bKb Co · +91…*, address label *(Friend)* and the landmark |
| Pressing **Cancel order** after the kitchen accepted (a mis-tap: the layout shifted) | Refused: *"Too late to cancel here. Please contact the restaurant."* |
| `docker restart foodbot` while the order was *preparing* | Order continued: **exactly one** each of picked-up, live-location map, halfway, almost-there, delivered, rating prompt (checked in the page text); nothing duplicated, nothing lost |

## Not exercised live
- **Kitchen rejection via the admin button.** The simulated kitchen accepts within seconds; my first click landed after acceptance. Covered by `tests/test_fulfilment.py`.
- **Rate limiting.** The tester's account is the admin, and admins are deliberately exempt from the limiter, so it cannot be triggered from this account. Covered by `tests/test_ops.py`.
- **GPS pin and voice notes.** Telegram Web has no location picker, and there is no microphone. Covered by `tests/test_addresses.py` and the voice tests.
- **The LLM paths.** The free daily token allowance of the production model was used up by the red-team recording, so the bot answered from the rules only (the designed degradation). Not a defect; noted so nobody reads these results as LLM coverage.

---

# Round 3: new features, live on Telegram Web (2026-10-07, ~08:30 IST, production model qwen3.8-27b)
| Flow | Result |
|---|---|
| `order again` | Lists the last three delivered orders as buttons, with the note that prices, availability and hours are re-checked |
| Reorder of orders from two late-night kitchens at 08:32 | Refused with the reason: *"Moonlight Kitchen is closed right now (open 9:00 pm - 4:00 am)"*; the cart was left alone |
| `idli vada for 3 under 400` → select → checkout → confirm to the friend's address | Order #5 placed; the bot immediately offered *"Looks like a group order. Split the bill between how many people?"*; tapping 3 gave *"total ₹225 / 3 → ₹75 each (includes ₹15 delivery, split equally)"* |
| Address prompt after enabling `MINIAPP_URL` | The reply keyboard shows **🗺 Pick on map** next to *Share location*; tapping it makes Telegram Web ask permission to open the web app, then creates the web-app panel |
| A photo (synthetic image of a dosa with the words "MASALA DOSA" drawn on it) | *"📸 Looks like: masala dosa (AI-assisted guess). Not right? Just type what you'd like..."* followed by three real dosa options for the friend's address |

## Not verified
- **The Mini App inside Telegram.** The web-app panel stayed on Telegram's loading placeholder for about 15 seconds. The same page, opened directly at its GitHub Pages address, renders the map, pin and button correctly, its Leaflet integrity hashes match the CDN files, and the bot side (payload validation, label step) is covered by 79 tests. I could not tell whether the blank panel is the Telegram Web client or something in the page, so treat the in-Telegram round trip as **unproven**; check it on a phone.
- **Recognition quality of the photo feature.** The test image had the dish name written on it, so this shows the plumbing (download, vision call, grounding, search), not that the model recognises real food photos. A photo costs about 2,000 tokens, five times a text message.
- **A successful reorder.** Both late-night kitchens were closed at the time, so only the refusal path was exercised live; the success path is covered by `tests/test_reorder.py`.
