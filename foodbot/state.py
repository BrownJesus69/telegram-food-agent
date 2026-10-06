"""Runtime facts shared between the bot, the simulator and the ops server (health checks, dashboard)."""
from __future__ import annotations

import time

started_at: float = time.time()
telegram_ok_at: float | None = None      # last successful round-trip to Telegram (heartbeat)
sim_tick_at: float | None = None         # last simulator pass
backup_at: float | None = None


def age(ts: float | None) -> float | None:
    return None if ts is None else max(0.0, time.time() - ts)
