"""Operations: metrics, health checks, dashboard security, rate limiting, error net, logging, backups."""
import asyncio
import json
import logging
import sqlite3
import time

import pytest
from aiohttp.test_utils import TestClient, TestServer

from foodbot import config, db, healthcheck, maintenance, metrics, observability, ops, orders, state, stats
from foodbot.services import catalogue
from foodbot.services.search import search_items

from .bot_harness import ADMIN, CUSTOMER
from .conftest import KORAMANGALA, NOON


@pytest.fixture(autouse=True)
def runtime_state(monkeypatch):
    monkeypatch.setattr(state, "telegram_ok_at", time.time())
    monkeypatch.setattr(state, "sim_tick_at", time.time())
    monkeypatch.setattr(config, "SIMULATE_DELIVERY", True)
    monkeypatch.setattr(config, "ADMIN_IDS", {ADMIN})


def place_order(key="k1"):
    db.add_address(CUSTOMER, "Home", "Koramangala flat", *KORAMANGALA, "Tester")
    hit = next(r for r in search_items("biryani", *KORAMANGALA, limit=50, now=NOON) if r.item.price * 2 >= r.restaurant.min_order)
    orders.clear_cart(CUSTOMER)
    orders.add_item(CUSTOMER, hit.item.id, 2)
    db.set_field(CUSTOMER, pending_key=key)
    return orders.create_order(CUSTOMER, key)[0]


# --------------------------------------------------------------------------------- metrics
def test_metrics_exposition_format():
    reg = metrics.Registry()
    c = reg.counter("t_total", "a counter")
    c.inc(kind="a")
    c.inc(2, kind="a")
    c.inc(kind="b")
    h = reg.histogram("t_seconds", "a histogram", buckets=(0.1, 1))
    for v in (0.05, 0.5, 3):
        h.observe(v)
    out = reg.render()
    assert 't_total{kind="a"} 3' in out and 't_total{kind="b"} 1' in out
    assert 't_seconds_bucket{le="0.1"} 1' in out and 't_seconds_bucket{le="1"} 2' in out and 't_seconds_bucket{le="+Inf"} 3' in out
    assert "t_seconds_count 3" in out and "# TYPE t_total counter" in out
    assert h.quantile(0.5) == 1 and metrics.Histogram("x", "x").quantile(0.5) is None


def test_label_values_cannot_break_the_exposition_format():
    c = metrics.Counter("x_total", "x")
    c.inc(source='bad"label\\with\nnewline')
    rendered = list(c.render())
    line = next(ln for ln in rendered if ln.startswith("x_total{"))
    assert "\n" not in line and line.endswith(" 1") and '\\"' in line and "\\n" in line and len(rendered) == 3


# --------------------------------------------------------------------------------- health
def test_health_ok_and_each_failure_is_detected(monkeypatch):
    ok, body = ops.health()
    assert ok and body["status"] == "ok" and set(body["checks"]) == {"database", "catalogue", "telegram", "simulator"}
    monkeypatch.setattr(state, "started_at", time.time() - 3600)                       # past the boot grace period
    monkeypatch.setattr(state, "telegram_ok_at", time.time() - 900)
    ok, body = ops.health()
    assert not ok and body["checks"]["telegram"]["ok"] is False
    monkeypatch.setattr(state, "telegram_ok_at", time.time())
    monkeypatch.setattr(state, "sim_tick_at", time.time() - 120)
    assert not ops.health()[0]
    monkeypatch.setattr(config, "SIMULATE_DELIVERY", False)                              # simulator not required when it is off
    assert ops.health()[0]
    monkeypatch.setattr(db, "DB_PATH", "/nonexistent-dir/x.db")
    ok, body = ops.health()
    assert not ok and body["checks"]["database"]["ok"] is False


# --------------------------------------------------------------------------------- web endpoints
async def test_endpoints_and_dashboard_security(monkeypatch):
    place_order()
    async with TestClient(TestServer(ops.make_app())) as client:
        r = await client.get("/healthz")
        assert r.status == 200 and (await r.json())["status"] == "ok"
        m = await (await client.get("/metrics")).text()
        for series in ("foodbot_uptime_seconds", "foodbot_catalogue_items", "foodbot_orders{status=\"PENDING\"} 1", "foodbot_llm_breaker_open"):
            assert series in m, series

        # no key configured: the dashboard and the data API do not exist
        assert (await client.get("/dashboard")).status == 404 and (await client.get("/api/stats")).status == 404

        monkeypatch.setattr(config, "DASHBOARD_KEY", "s3cret-key")
        assert (await client.get("/dashboard")).status == 404
        assert (await client.get("/api/stats?key=wrong")).status == 404
        assert (await client.get("/api/stats?key=s3cret-ke")).status == 404                 # prefix is not enough
        ok = await client.get("/dashboard?key=s3cret-key")
        assert ok.status == 200 and "FoodBot" in await ok.text()
        assert "default-src 'none'" in ok.headers["Content-Security-Policy"] and ok.headers["Cache-Control"] == "no-store"
        data = await (await client.get("/api/stats", headers={"X-Dashboard-Key": "s3cret-key"})).json()
        assert data["orders"]["total"] == 1 and data["system"]["restaurants"] == len(catalogue.RESTAURANTS)
        # health and metrics never leak customer data
        assert "Tester" not in await (await client.get("/healthz")).text() and "Tester" not in m


def test_dashboard_never_renders_untrusted_text_as_html():
    html = ops.DASHBOARD_HTML
    assert "innerHTML" not in html and "document.write" not in html and "eval(" not in html
    assert "textContent" in html                                                           # recipient names are user-controlled


# --------------------------------------------------------------------------------- stats
async def test_stats_reflect_orders_funnel_and_ratings(bot_env):
    env = bot_env
    db.add_address(CUSTOMER, "Home", "Koramangala flat", *KORAMANGALA, "Tester")
    await env.say(CUSTOMER, "chicken biryani")
    await env.press(CUSTOMER, env.button("sel:"))
    await env.press(CUSTOMER, "checkout")
    await env.press(CUSTOMER, "skip_landmark")
    s = stats.collect()
    kinds = {f["label"]: f["all"] for f in s["funnel"]}
    assert kinds["Searched"] >= 1 and kinds["Added to cart"] >= 1 and kinds["Started checkout"] >= 1 and kinds["Placed order"] == 0
    assert s["ai"]["reading_sources"].get("rules", 0) >= 1

    oid = place_order("k9")
    for status in ("ACCEPTED", "PREPARING", "OUT_FOR_DELIVERY", "DELIVERED"):
        await env.press(ADMIN, f"adm:{status}:{oid}")
    await env.press(CUSTOMER, f"rate:{oid}:5")
    s = stats.collect()
    total = orders.get_order(oid)[0]["total"]
    assert s["orders"]["total"] == 1 and s["orders"]["gmv"] == total and s["orders"]["avg_rating"] == 5
    assert s["orders"]["by_status"]["DELIVERED"]["n"] == 1 and sum(s["orders"]["hourly"]) == 1
    assert s["live"][0]["status"] == "DELIVERED" and s["live"][0]["rider"]
    assert sum(d["qty"] for d in s["top_dishes"]) == 2
    assert s["ai"]["eval"]["heldout"]["full"] > 80                                         # parsed from evals/RESULTS.md


async def test_stats_command_is_admin_only(bot_env):
    env, session = bot_env, bot_env.session
    await env.say(CUSTOMER, "/stats")
    assert not any("FoodBot v" in t for t in session.texts(CUSTOMER))
    await env.say(ADMIN, "/stats")
    assert any("FoodBot v" in t and "Funnel" in t for t in session.texts(ADMIN))


# --------------------------------------------------------------------------------- rate limiting + error net
def test_token_bucket_burst_refill_and_isolation():
    now = [0.0]
    b = observability.TokenBucket(3, 1.0, clock=lambda: now[0])
    assert [b.allow(1) for _ in range(4)] == [True, True, True, False]
    assert b.allow(2)                                                                      # other users are unaffected
    now[0] += 2
    assert b.allow(1) and b.allow(1) and not b.allow(1)                                    # two tokens refilled
    now[0] += 100
    assert [b.allow(1) for _ in range(4)] == [True, True, True, False]                     # capped at the burst size


async def test_flooding_user_is_throttled_but_admin_and_others_are_not(bot_env, monkeypatch):
    monkeypatch.setattr(config, "THROTTLE_BURST", 3)
    monkeypatch.setattr(config, "THROTTLE_PER_SECOND", 0.0)
    from .bot_harness import BotEnv
    env = BotEnv()
    before = metrics.RATE_LIMITED.total()
    for _ in range(8):
        await env.say(CUSTOMER, "hi")
    greetings = [t for t in env.session.texts(CUSTOMER) if "Hello" in t]
    assert len(greetings) == 3 and metrics.RATE_LIMITED.total() - before == 5
    assert sum("very fast" in t for t in env.session.texts(CUSTOMER)) == 1                 # one polite warning, not a flood of them
    for _ in range(6):
        await env.say(ADMIN, "hi")                                                         # admins are exempt
    assert sum("Hello" in t for t in env.session.texts(ADMIN)) == 6
    await env.say(2, "hi")
    assert any("Hello" in t for t in env.session.texts(2))


async def test_handler_crash_is_contained_reported_and_counted(bot_env, monkeypatch, caplog):
    from foodbot import handlers

    async def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(handlers, "show_tracking", boom)
    before = metrics.UPDATE_ERRORS.total()
    with caplog.at_level(logging.ERROR):
        await bot_env.say(CUSTOMER, "/track")
    assert "Something went wrong" in bot_env.session.last_text()
    assert metrics.UPDATE_ERRORS.total() == before + 1
    assert any("kaboom" in (r.exc_text or "") or r.exc_info for r in caplog.records)
    await bot_env.say(CUSTOMER, "hi")                                                      # the bot keeps serving afterwards
    assert any("Hello" in t for t in bot_env.session.texts(CUSTOMER))


# --------------------------------------------------------------------------------- logging
def test_json_logs_carry_update_context_and_exceptions(capsys):
    observability.setup_logging("json")
    log = logging.getLogger("foodbot.test")
    token = observability.update_ctx.set({"update_id": 42, "user_id": 7})
    try:
        try:
            raise ValueError("bad")
        except ValueError:
            log.exception("it failed")
    finally:
        observability.update_ctx.reset(token)
    line = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert line["msg"] == "it failed" and line["update_id"] == 42 and line["user_id"] == 7 and "ValueError" in line["exc"]
    assert line["level"] == "ERROR" and "ts" in line


# --------------------------------------------------------------------------------- maintenance
def test_backup_is_a_consistent_copy_and_old_ones_are_pruned(tmp_path):
    place_order()
    for _ in range(5):
        path = maintenance.backup_db(tmp_path / "bk", keep=3)
    assert len(list((tmp_path / "bk").glob("foodbot-*.db"))) == 3
    copy = sqlite3.connect(path)
    assert copy.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 1
    assert copy.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    copy.close()
    assert state.backup_at is not None


def test_old_events_are_pruned():
    db.log_event("search", 1)
    conn = db.connect()
    with conn:
        conn.execute("INSERT INTO events(ts, kind) VALUES('2020-01-01T00:00:00+00:00', 'search')")
    conn.close()
    assert maintenance.prune_events(days=30) == 1
    assert db.connect().execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1


def test_log_event_never_raises(monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", "/nonexistent-dir/x.db")
    db.log_event("search", 1, found=3)                                                     # analytics must not break a user flow


# --------------------------------------------------------------------------------- container healthcheck
async def test_container_healthcheck_follows_the_server(monkeypatch):
    runner = await ops.start("127.0.0.1", 0)
    port = runner.addresses[0][1]
    monkeypatch.setattr(config, "OPS_PORT", port)
    assert await asyncio.to_thread(healthcheck.main) == 0
    monkeypatch.setattr(state, "started_at", time.time() - 3600)
    monkeypatch.setattr(state, "telegram_ok_at", time.time() - 3600)                       # unhealthy -> 503 -> exit code 1
    assert await asyncio.to_thread(healthcheck.main) == 1
    await runner.cleanup()
    assert await asyncio.to_thread(healthcheck.main) == 1                                  # server gone -> unhealthy
