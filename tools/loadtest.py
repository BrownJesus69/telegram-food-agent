"""Load test: many simulated customers through the real dispatcher at once.

    python -m tools.loadtest --users 50 --out docs/LOADTEST.md

Every user does the full journey (start, share a pin, name the address, search in plain words, add to cart, check out,
confirm). Telegram's HTTP layer is replaced by the in-memory recorder from the test-suite, so this measures what the bot itself
costs (parsing, planning, SQLite, rendering), not Telegram's network latency. The bot is a single asyncio process with a
synchronous SQLite driver, so the numbers show how updates queue behind each other under concurrency.
"""
from __future__ import annotations

import argparse
import asyncio
import platform
import statistics
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

from foodbot import config, db
from foodbot.services import catalogue
from tests.bot_harness import ADMIN, BotEnv

NOON = datetime(2026, 10, 6, 13, 0, tzinfo=catalogue.IST)
KORAMANGALA = (12.9352, 77.6245)
SEARCHES = ["chicken biryani under 300", "masala dosa and filter coffee", "light dinner for 2 under 500, no onion garlic",
            "feed 4 people, 2 veg and 2 non veg under 1500", "ondu masala dose", "paneer tikka no onion garlic"]


class Timer:
    def __init__(self):
        self.samples: dict[str, list[float]] = {}

    async def run(self, step: str, coro):
        t0 = time.perf_counter()
        await coro
        self.samples.setdefault(step, []).append((time.perf_counter() - t0) * 1000)


def pct(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


async def journey(env: BotEnv, uid: int, timer: Timer, search: str):
    session = env.session
    await timer.run("/start", env.say(uid, "/start"))
    await timer.run("share a pin", env.send_location(uid, *KORAMANGALA))
    await timer.run("name the address", env.press(uid, "addr:lbl:home"))
    await timer.run("search in plain words", env.say(uid, search))
    picks = [b for b in session.buttons(uid) if b.startswith(("sel:", "plan:"))]
    if not picks:
        return "no orderable result"
    await timer.run("add to cart", env.press(uid, picks[-1]))
    for _ in range(4):                                       # a kitchen's minimum order: tap + like a customer would
        if "minimum order" not in session.last_text(uid) or not picks[-1].startswith("sel:"):
            break
        await timer.run("change quantity", env.press(uid, "inc:" + picks[-1].split(":")[1]))
    await timer.run("checkout", env.press(uid, "checkout"))
    await timer.run("skip landmark", env.press(uid, "skip_landmark"))
    confirm = [b for b in session.buttons(uid) if b.startswith("confirm:")]
    if not confirm:
        return "cart blocked: " + " ".join(session.last_text(uid).split())[-70:]
    await timer.run("confirm order", env.press(uid, confirm[-1]))
    return "ok"


async def main_async(users: int, out: Path | None) -> int:
    from unittest import mock

    catalogue.load()
    tmp = tempfile.mkdtemp()
    with mock.patch.object(db, "DB_PATH", str(Path(tmp) / "load.db")), mock.patch.object(catalogue, "now_ist", lambda: NOON), \
            mock.patch.object(config, "THROTTLE_BURST", 10_000), mock.patch.object(config, "ADMIN_IDS", {ADMIN}), \
            mock.patch.object(config, "GROQ_API_KEY", ""), mock.patch.object(config, "GEOAPIFY_API_KEY", ""), mock.patch.object(config, "SIMULATE_DELIVERY", False):
        db.init_db()
        env = BotEnv()
        timer = Timer()
        ids = list(range(1000, 1000 + users))
        started = time.perf_counter()
        results = await asyncio.gather(*(journey(env, uid, timer, SEARCHES[i % len(SEARCHES)]) for i, uid in enumerate(ids)))
        wall = time.perf_counter() - started
        orders = len(__import__("foodbot.orders", fromlist=["x"]).recent_orders(10_000))
    updates = sum(len(v) for v in timer.samples.values())
    lines = [f"# Load test: {users} customers at once", "",
             f"Run: {datetime.now().strftime('%Y-%m-%d %H:%M')} on {platform.system()} {platform.machine()}, Python {platform.python_version()}, "
             "one process, SQLite (WAL), Telegram HTTP replaced by an in-memory recorder (no network latency included).", "",
             f"**{users} concurrent customers, {updates} updates in {wall:.1f} s = {updates / wall:.0f} updates/s; "
             f"{orders} orders placed ({results.count('ok')}/{users} journeys completed).**", "",
             "| Step | n | p50 | p95 | p99 | max |", "|---|---|---|---|---|---|"]
    for step, vals in timer.samples.items():
        lines.append(f"| {step} | {len(vals)} | {statistics.median(vals):.0f} ms | {pct(vals, .95):.0f} ms | {pct(vals, .99):.0f} ms | {max(vals):.0f} ms |")
    blocked: dict[str, int] = {}
    for i, r in enumerate(results):
        if r != "ok":
            key = f"{SEARCHES[i % len(SEARCHES)]!r}: {r}"
            blocked[key] = blocked.get(key, 0) + 1
    if blocked:
        lines += ["", "Journeys that did not reach an order (the search found nothing orderable for the shared pin, or the cart was blocked by a "
                  "kitchen rule such as its minimum order):", *[f"- {k} (x{n})" for k, n in blocked.items()]]
    every = [v for vals in timer.samples.values() for v in vals]
    lines += ["", f"All updates together: p50 {statistics.median(every):.0f} ms, p95 {pct(every, .95):.0f} ms, p99 {pct(every, .99):.0f} ms.", "",
              "How to read it: all customers start together, so each update waits behind the others' (single event loop, synchronous SQLite). "
              "The per-step latency is therefore a worst case for 'N people tapping at the same instant'; a steady 50 users would see roughly the p50.", ""]
    report = "\n".join(lines)
    print(report)
    if out:
        out.write_text(report, encoding="utf-8")
    return 0


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", type=int, default=50)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    raise SystemExit(asyncio.run(main_async(args.users, args.out)))


if __name__ == "__main__":
    main()
