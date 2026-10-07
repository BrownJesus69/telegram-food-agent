"""Numbers for the ops dashboard and the /stats admin command, computed from the database and in-process state."""
from __future__ import annotations

import json
import platform
import re
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import foodbot
from foodbot import config, db, state
from foodbot.concierge import llm
from foodbot.services import catalogue

RESULTS = Path(config.BASE_DIR) / "evals" / "RESULTS.md"
FUNNEL = (("search", "Searched"), ("cart_add", "Added to cart"), ("checkout_start", "Started checkout"), ("order_placed", "Placed order"))


def _eval_summary() -> dict:
    """Pass rates from evals/RESULTS.md ({'dev': {'rules': 99.1, ...}, 'heldout': {...}}), empty if the file is absent."""
    try:
        text = RESULTS.read_text(encoding="utf-8")
    except OSError:
        return {}
    out: dict[str, Any] = {}
    section = None
    for line in text.splitlines():
        if line.startswith("# "):
            section = "heldout" if "held-out" in line else "dev" if "dev" in line else None
        m = re.match(r"\| (rules|llm|cascade|full) \| (\d+)/(\d+) \|", line)
        if m and section:
            out.setdefault(section, {})[m.group(1)] = round(100 * int(m.group(2)) / int(m.group(3)), 1)
    return out


def collect(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    conn = db.connect()
    try:
        by_status = {r["status"]: {"n": r["n"], "total": r["gmv"] or 0}
                     for r in conn.execute("SELECT status, COUNT(*) n, SUM(total) gmv FROM orders GROUP BY status")}
        orders_total = sum(v["n"] for v in by_status.values())
        placed = [v for k, v in by_status.items() if k not in ("CANCELLED", "REJECTED")]
        aov = (sum(v["total"] for v in placed) / max(sum(v["n"] for v in placed), 1)) if placed else 0
        rating = conn.execute("SELECT AVG(rating) a, COUNT(rating) n FROM orders WHERE rating IS NOT NULL").fetchone()
        dur = conn.execute(
            "SELECT AVG((julianday(delivered_at)-julianday(created_at))*86400) s FROM orders WHERE delivered_at IS NOT NULL"
        ).fetchone()["s"]

        since = (now - timedelta(hours=24)).isoformat(timespec="seconds")
        hourly = [0] * 24
        for r in conn.execute("SELECT created_at FROM orders WHERE created_at >= ?", (since,)):
            age_h = int((now - datetime.fromisoformat(r["created_at"])).total_seconds() // 3600)
            if 0 <= age_h < 24:
                hourly[23 - age_h] += 1

        ev_all = {r["kind"]: r["n"] for r in conn.execute("SELECT kind, COUNT(*) n FROM events GROUP BY kind")}
        ev_24 = {r["kind"]: r["n"] for r in conn.execute("SELECT kind, COUNT(*) n FROM events WHERE ts >= ? GROUP BY kind", (since,))}
        sources: Counter[str] = Counter()
        for r in conn.execute("SELECT data FROM events WHERE kind='search' ORDER BY id DESC LIMIT 500"):
            try:
                sources[json.loads(r["data"] or "{}").get("source", "rules")] += 1
            except ValueError:
                pass

        dishes = [{"name": r["item_name"], "qty": r["q"]} for r in conn.execute(
            "SELECT item_name, SUM(quantity) q FROM order_items GROUP BY item_name ORDER BY q DESC, item_name LIMIT 5")]
        kitchens = []
        for r in conn.execute("SELECT restaurant_id, COUNT(*) n FROM orders GROUP BY restaurant_id ORDER BY n DESC LIMIT 5"):
            rest = catalogue.get_restaurant(r["restaurant_id"])
            kitchens.append({"name": rest.name if rest else r["restaurant_id"], "orders": r["n"]})

        live = []
        for r in conn.execute(
            "SELECT o.id, o.status, o.total, o.restaurant_id, o.created_at, o.recipient_name, o.address_label, c.name rider "
            "FROM orders o LEFT JOIN order_courier c ON c.order_id=o.id ORDER BY o.id DESC LIMIT 12"
        ):
            rest = catalogue.get_restaurant(r["restaurant_id"])
            live.append({
                "id": r["id"], "status": r["status"], "total": r["total"], "kitchen": rest.name if rest else r["restaurant_id"],
                "to": f"{r['recipient_name'] or '-'} ({r['address_label'] or '-'})", "rider": r["rider"],
                "age_s": int((now - datetime.fromisoformat(r["created_at"])).total_seconds()),
            })
        users = conn.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
        with_addr = conn.execute("SELECT COUNT(DISTINCT telegram_id) n FROM addresses WHERE deleted=0").fetchone()["n"]
    finally:
        conn.close()

    client = llm.default_client()
    lat = sorted(client.stats["latency_ms"])
    try:
        db_kb = round(Path(db.DB_PATH).stat().st_size / 1024)
    except OSError:
        db_kb = None
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "orders": {"total": orders_total, "by_status": by_status, "gmv": by_status.get("DELIVERED", {}).get("total", 0),
                   "aov": round(aov), "avg_rating": round(rating["a"], 2) if rating["a"] else None, "ratings": rating["n"],
                   "avg_delivery_demo_s": round(dur) if dur else None,
                   "avg_delivery_catalogue_min": round(dur / max(config.SIM_SECONDS_PER_MINUTE, 0.01)) if dur else None,
                   "hourly": hourly},
        "funnel": [{"label": label, "last24h": ev_24.get(k, 0), "all": ev_all.get(k, 0)} for k, label in FUNNEL],
        "top_dishes": dishes, "top_kitchens": kitchens, "live": live,
        "users": {"total": users, "with_address": with_addr},
        "ai": {
            "model": client.model, "has_key": bool(client.api_key), "breaker_open": client.breaker.is_open,
            "calls": client.stats["calls"], "ok": client.stats["ok"], "failed": client.stats["failed"],
            "cache_hits": client.stats["cache_hits"], "tokens": client.stats["tokens"],
            "p50_ms": lat[len(lat) // 2] if lat else None, "p95_ms": lat[int(len(lat) * 0.95)] if lat else None,
            "reading_sources": dict(sources), "eval": _eval_summary(),
        },
        "system": {
            "version": foodbot.__version__, "python": platform.python_version(), "uptime_s": round(time.time() - state.started_at),
            "restaurants": len(catalogue.RESTAURANTS), "menu_items": len(catalogue.ITEMS), "simulation": config.SIMULATE_DELIVERY,
            "telegram_ok_age_s": _r(state.age(state.telegram_ok_at)), "simulator_tick_age_s": _r(state.age(state.sim_tick_at)),
            "last_backup_age_s": _r(state.age(state.backup_at)), "db_kb": db_kb,
        },
    }


def _r(v):
    return None if v is None else round(v, 1)


def summary_text(s: dict | None = None) -> str:
    """Compact version for the admin's /stats command."""
    s = s or collect()
    o, ai, sys_ = s["orders"], s["ai"], s["system"]
    funnel = " → ".join(f"{f['label'].split()[0].lower()} {f['last24h']}" for f in s["funnel"])
    status = ", ".join(f"{k.lower().replace('_', ' ')} {v['n']}" for k, v in sorted(o["by_status"].items())) or "none yet"
    return (
        f"📊 <b>FoodBot v{sys_['version']}</b> · up {sys_['uptime_s'] // 3600}h {sys_['uptime_s'] % 3600 // 60}m\n"
        f"Orders: {o['total']} ({status})\nGMV delivered ₹{o['gmv']} · AOV ₹{o['aov']} · rating {o['avg_rating'] or '–'} ({o['ratings']})\n"
        f"Funnel (24h): {funnel}\nUsers: {s['users']['total']} ({s['users']['with_address']} with an address)\n"
        f"AI: {ai['calls']} calls ({ai['failed']} failed), {ai['tokens']} tokens, breaker {'OPEN' if ai['breaker_open'] else 'closed'}, "
        f"readings {ai['reading_sources'] or '–'}\n"
        f"Catalogue: {sys_['restaurants']} kitchens, {sys_['menu_items']} items · simulation {'on' if sys_['simulation'] else 'off'}"
    )
