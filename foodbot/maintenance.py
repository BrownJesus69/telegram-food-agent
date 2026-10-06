"""Housekeeping: consistent SQLite backups (online, via the backup API) and event pruning."""
from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from foodbot import config, db, state

log = logging.getLogger(__name__)


def backup_db(dest_dir: str | Path | None = None, keep: int = 7) -> Path:
    """Copy the live database to <dest>/foodbot-<utc timestamp>.db without stopping the bot; keep the newest `keep`."""
    dest = Path(dest_dir or config.BACKUP_DIR)
    dest.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    target, n = dest / f"foodbot-{stamp}.db", 0
    while target.exists():            # a coarse clock (Windows) can repeat a timestamp; never overwrite an earlier backup
        n += 1
        target = dest / f"foodbot-{stamp}{n:02d}.db"        # '0' sorts after '.', so the newest still sorts last
    src = db.connect()
    try:
        out = sqlite3.connect(target)
        try:
            src.backup(out)                                  # consistent snapshot even while writers are active (WAL)
        finally:
            out.close()
    finally:
        src.close()
    for old in sorted(dest.glob("foodbot-*.db"))[:-keep]:
        old.unlink(missing_ok=True)
    state.backup_at = time.time()
    return target


def prune_events(days: int = 30) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    conn = db.connect()
    try:
        with conn:
            return conn.execute("DELETE FROM events WHERE ts < ?", (cutoff,)).rowcount
    finally:
        conn.close()


async def run():
    """Back up shortly after start and then every BACKUP_EVERY_HOURS. Never raises."""
    await asyncio.sleep(30)
    while True:
        try:
            path = await asyncio.to_thread(backup_db)
            pruned = await asyncio.to_thread(prune_events)
            log.info("backup written to %s (pruned %d old events)", path.name, pruned)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("backup failed")
        await asyncio.sleep(max(config.BACKUP_EVERY_HOURS, 0.1) * 3600)
