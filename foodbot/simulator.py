"""Kitchen + rider simulator: moves orders through their lifecycle on a demo clock so the system can be shown end to end.

Stateless by design: when something is due is derived from the order row (`updated_at`, status) and the courier row
(`pickup_at`, `travel_s`), never from in-memory timers. A restart therefore resumes mid-delivery. Humans stay in
charge: an admin pressing a button simply moves the order earlier, and the simulator carries on from the new state.
"""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone

from foodbot import config, db, fulfilment, orders
from foodbot.services import catalogue

log = logging.getLogger(__name__)

NEXT = {"PENDING": "ACCEPTED", "ACCEPTED": "PREPARING", "PREPARING": "OUT_FOR_DELIVERY"}


def stage_delay_seconds(order) -> float:
    """How long the order rests in its current status before the simulated kitchen moves it on."""
    status = order["status"]
    if status == "PENDING":
        return config.SIM_ACCEPT_SECONDS * (0.6 + 0.8 * random.Random(f"accept:{order['id']}").random())
    if status == "ACCEPTED":
        return 3.0
    if status == "PREPARING":
        rest = catalogue.get_restaurant(order["restaurant_id"])
        prep = rest.prep_min if rest else 15
        return min(max(prep * config.SIM_SECONDS_PER_MINUTE, 8.0), 300.0)
    return float("inf")


def rejects(order) -> bool:
    """Deterministic per order so a restart cannot flip the decision."""
    return config.SIM_REJECT_RATE > 0 and random.Random(f"reject:{order['id']}").random() < config.SIM_REJECT_RATE


async def tick(bot, now: datetime | None = None) -> int:
    """One scheduler pass over every active order. Returns how many state changes or ride updates it made."""
    if not config.SIMULATE_DELIVERY:
        return 0
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    changed = 0
    for order in orders.active_orders():
        oid = order["id"]
        try:
            if order["status"] == "OUT_FOR_DELIVERY":
                rider = db.get_courier(oid)
                if rider is None or not rider["pickup_at"]:
                    continue
                if await fulfilment.tick_ride(bot, order, rider, now):
                    await fulfilment.advance(bot, oid, "DELIVERED", "delivered by simulated rider", now)
                changed += 1
                continue
            due = datetime.fromisoformat(order["updated_at"]) .timestamp() + stage_delay_seconds(order)
            if now.timestamp() < due:
                continue
            if order["status"] == "PENDING" and rejects(order):
                await fulfilment.advance(bot, oid, "REJECTED", "Item unavailable", now)
            else:
                await fulfilment.advance(bot, oid, NEXT[order["status"]], "simulated kitchen", now)
            changed += 1
        except orders.OrderError:
            continue                                  # an admin or the customer moved it first; nothing to do
        except Exception:
            log.exception("simulator failed on order #%s", oid)
    return changed


async def run(bot):
    """Background loop started by the app. Never raises: a bad tick must not take the bot down."""
    log.info("delivery simulator running (tick %.1fs, %.1fs per catalogue minute)", config.SIM_TICK_SECONDS, config.SIM_SECONDS_PER_MINUTE)
    while True:
        try:
            await tick(bot)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("simulator tick crashed")
        await asyncio.sleep(config.SIM_TICK_SECONDS)
