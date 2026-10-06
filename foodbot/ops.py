"""Operations server: /healthz (liveness + dependency checks), /metrics (Prometheus) and a protected ops dashboard.

/healthz and /metrics carry no customer data. The dashboard and /api/stats show orders and recipient names, so they are
disabled unless DASHBOARD_KEY is set, and the key is compared in constant time. In docker-compose the port is published
on 127.0.0.1 only.
"""
from __future__ import annotations

import hmac
import logging
import sqlite3

from aiohttp import web

import foodbot
from foodbot import config, db, metrics, state, stats
from foodbot.concierge import llm
from foodbot.services import catalogue

log = logging.getLogger(__name__)
GRACE_S = 90        # right after boot nothing has had time to report yet


def health() -> tuple[bool, dict]:
    up = state.age(state.started_at) or 0
    checks: dict[str, dict] = {}
    try:
        conn = db.connect()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        checks["database"] = {"ok": True}
    except sqlite3.Error as e:
        checks["database"] = {"ok": False, "detail": type(e).__name__}
    checks["catalogue"] = {"ok": len(catalogue.RESTAURANTS) > 0 and len(catalogue.ITEMS) > 0,
                           "detail": f"{len(catalogue.RESTAURANTS)} kitchens, {len(catalogue.ITEMS)} items"}
    tg_age = state.age(state.telegram_ok_at)
    checks["telegram"] = {"ok": (tg_age is not None and tg_age < 300) or (tg_age is None and up < GRACE_S),
                          "detail": "no heartbeat yet" if tg_age is None else f"last ok {tg_age:.0f}s ago"}
    if config.SIMULATE_DELIVERY:
        sim_age = state.age(state.sim_tick_at)
        checks["simulator"] = {"ok": (sim_age is not None and sim_age < 30) or (sim_age is None and up < GRACE_S),
                               "detail": "no tick yet" if sim_age is None else f"last tick {sim_age:.0f}s ago"}
    ok = all(c["ok"] for c in checks.values())
    return ok, {"status": "ok" if ok else "degraded", "version": foodbot.__version__, "uptime_s": round(up), "checks": checks}


@metrics.REGISTRY.collector
def _runtime_collector():
    lines = []
    lines += metrics.gauge_lines("foodbot_uptime_seconds", "Process uptime", state.age(state.started_at))
    lines += metrics.gauge_lines("foodbot_telegram_last_ok_age_seconds", "Seconds since the last successful Telegram call", state.age(state.telegram_ok_at))
    lines += metrics.gauge_lines("foodbot_simulator_tick_age_seconds", "Seconds since the last simulator pass", state.age(state.sim_tick_at))
    lines += metrics.gauge_lines("foodbot_catalogue_kitchens", "Kitchens loaded", len(catalogue.RESTAURANTS))
    lines += metrics.gauge_lines("foodbot_catalogue_items", "Menu items loaded", len(catalogue.ITEMS))
    client = llm.default_client()
    for outcome in ("ok", "failed", "cache_hits"):
        lines += metrics.gauge_lines("foodbot_llm_calls", "LLM calls by outcome", client.stats[outcome], outcome=outcome)
    lines += metrics.gauge_lines("foodbot_llm_tokens", "LLM tokens used", client.stats["tokens"])
    lines += metrics.gauge_lines("foodbot_llm_breaker_open", "1 while the LLM circuit breaker is open", int(client.breaker.is_open))
    try:
        conn = db.connect()
        for r in conn.execute("SELECT status, COUNT(*) n FROM orders GROUP BY status"):
            lines += metrics.gauge_lines("foodbot_orders", "Orders by current status", r["n"], status=r["status"])
        conn.close()
    except sqlite3.Error:
        pass
    return lines


# --------------------------------------------------------------------------------- handlers
def _authorised(request: web.Request) -> bool:
    key = config.DASHBOARD_KEY
    given = request.query.get("key", "") or request.headers.get("X-Dashboard-Key", "")
    return bool(key) and hmac.compare_digest(given.encode(), key.encode())


async def healthz(request: web.Request) -> web.Response:
    ok, body = health()
    return web.json_response(body, status=200 if ok else 503)


async def metrics_view(request: web.Request) -> web.Response:
    return web.Response(text=metrics.REGISTRY.render(), content_type="text/plain", charset="utf-8")


async def api_stats(request: web.Request) -> web.Response:
    if not _authorised(request):
        return web.Response(status=404)
    return web.json_response(stats.collect(), headers={"Cache-Control": "no-store"})


async def dashboard(request: web.Request) -> web.Response:
    if not _authorised(request):
        return web.Response(status=404)
    return web.Response(text=DASHBOARD_HTML, content_type="text/html", headers={"Cache-Control": "no-store", "X-Frame-Options": "DENY",
                        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'"})


async def root(request: web.Request) -> web.Response:
    raise web.HTTPFound("/dashboard" + ("?" + request.query_string if request.query_string else ""))


def make_app() -> web.Application:
    app = web.Application()
    app.add_routes([web.get("/healthz", healthz), web.get("/metrics", metrics_view), web.get("/api/stats", api_stats),
                    web.get("/dashboard", dashboard), web.get("/", root)])
    return app


async def start(host: str | None = None, port: int | None = None) -> web.AppRunner:
    runner = web.AppRunner(make_app(), access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, host or config.OPS_HOST, port or config.OPS_PORT)
    await site.start()
    log.info("ops server on http://%s:%s (health, metrics%s)", host or config.OPS_HOST, port or config.OPS_PORT,
             ", dashboard" if config.DASHBOARD_KEY else "; dashboard disabled: set DASHBOARD_KEY")
    return runner


DASHBOARD_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FoodBot Ops</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#14171c;--mute:#5d6673;--line:#e3e6eb;--accent:#e4572e;--ok:#1f9d55;--warn:#d98a00;--bad:#d64545;--bar:#e4572e;--bar2:#3b82f6}
@media (prefers-color-scheme:dark){:root{--bg:#0f1216;--card:#171b21;--ink:#e8ebf0;--mute:#97a1ae;--line:#262c35;--accent:#ff7a52;--bar:#ff7a52;--bar2:#6ea8ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
header{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;padding:16px 20px}
h1{font-size:18px;margin:0}h2{font-size:13px;letter-spacing:.04em;text-transform:uppercase;color:var(--mute);margin:0 0 10px}
main{display:grid;gap:14px;padding:0 20px 28px;grid-template-columns:repeat(12,1fr)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;min-width:0}
.kpis{grid-column:span 12;display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.kpi .v{font-size:26px;font-weight:650}.kpi .l{color:var(--mute);font-size:12px}
.c4{grid-column:span 4}.c6{grid-column:span 6}.c8{grid-column:span 8}.c12{grid-column:span 12}
@media (max-width:900px){.c4,.c6,.c8{grid-column:span 12}}
.pill{display:inline-block;padding:2px 9px;border-radius:99px;font-size:12px;font-weight:600;background:var(--line);color:var(--mute)}
.pill.ok{background:color-mix(in srgb,var(--ok) 18%,transparent);color:var(--ok)}.pill.bad{background:color-mix(in srgb,var(--bad) 18%,transparent);color:var(--bad)}
.pill.warn{background:color-mix(in srgb,var(--warn) 20%,transparent);color:var(--warn)}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);font-size:13px}th{color:var(--mute);font-weight:600}
.bar{display:flex;align-items:center;gap:8px;margin:6px 0}.bar .t{flex:0 0 120px;color:var(--mute);font-size:12px}
.bar .b{height:14px;border-radius:4px;background:var(--bar);min-width:2px}.bar .n{font-variant-numeric:tabular-nums}
.kv{display:grid;grid-template-columns:auto 1fr;gap:4px 14px;font-size:13px}.kv dt{color:var(--mute)}.kv dd{margin:0;font-variant-numeric:tabular-nums}
svg{width:100%;height:120px}.muted{color:var(--mute)}
</style></head><body>
<header><h1>FoodBot · Operations</h1><div><span id="health" class="pill">checking…</span> <span id="ver" class="muted"></span> <span id="upd" class="muted"></span></div></header>
<main id="m"><div class="card c12">Loading…</div></main>
<script>
const q = location.search;
const el = (t, c, x) => { const e = document.createElement(t); if (c) e.className = c; if (x !== undefined) e.textContent = x; return e; };
const card = (cls, title) => { const c = el('section', 'card ' + cls); if (title) c.append(el('h2', '', title)); return c; };
const dur = s => s == null ? '–' : s >= 3600 ? Math.floor(s/3600)+'h '+Math.floor(s%3600/60)+'m' : s >= 60 ? Math.floor(s/60)+'m '+(s%60)+'s' : s+'s';
function bars(rows, max) { const w = el('div'); const m = max || Math.max(1, ...rows.map(r => r[1]));
  rows.forEach(([t, n]) => { const r = el('div', 'bar'); r.append(el('span', 't', t)); const b = el('span', 'b'); b.style.width = (100 * n / m) + '%'; r.append(b, el('span', 'n', n)); w.append(r); }); return w; }
function hourly(vals) { const NS = 'http://www.w3.org/2000/svg', svg = document.createElementNS(NS, 'svg'); svg.setAttribute('viewBox', '0 0 240 100'); svg.setAttribute('role', 'img'); svg.setAttribute('aria-label', 'Orders per hour, last 24 hours');
  const mx = Math.max(1, ...vals); vals.forEach((v, i) => { const r = document.createElementNS(NS, 'rect'); const h = 90 * v / mx; r.setAttribute('x', i * 10 + 1); r.setAttribute('y', 95 - h); r.setAttribute('width', 8); r.setAttribute('height', Math.max(h, 1)); r.setAttribute('rx', 2); r.setAttribute('fill', v ? 'var(--bar)' : 'var(--line)'); svg.append(r); }); return svg; }
function kv(pairs) { const d = el('dl', 'kv'); pairs.forEach(([k, v]) => { d.append(el('dt', '', k), el('dd', '', v)); }); return d; }
const pill = (text, kind) => el('span', 'pill ' + (kind || ''), text);
async function load() {
  const [s, h] = await Promise.all([fetch('/api/stats' + q).then(r => r.json()), fetch('/healthz').then(r => r.json())]);
  const hp = document.getElementById('health'); hp.textContent = h.status; hp.className = 'pill ' + (h.status === 'ok' ? 'ok' : 'bad');
  document.getElementById('ver').textContent = 'v' + s.system.version; document.getElementById('upd').textContent = '· ' + s.generated_at.slice(11, 19) + ' UTC';
  const m = document.getElementById('m'); m.replaceChildren();
  const k = el('div', 'kpis'); const o = s.orders;
  [['Orders', o.total], ['Delivered GMV', '₹' + o.gmv], ['Avg order', '₹' + o.aov], ['Rating', o.avg_rating ? o.avg_rating + ' ★ (' + o.ratings + ')' : '–'],
   ['Avg delivery', o.avg_delivery_catalogue_min != null ? o.avg_delivery_catalogue_min + ' min' : '–']].forEach(([l, v]) => { const c = el('div', 'card kpi'); c.append(el('div', 'v', v), el('div', 'l', l)); k.append(c); });
  m.append(k);
  const f = card('c4', 'Funnel (last 24h)'); f.append(bars(s.funnel.map(x => [x.label, x.last24h]))); f.append(el('p', 'muted', 'All time: ' + s.funnel.map(x => x.all).join(' → '))); m.append(f);
  const hr = card('c8', 'Orders per hour (last 24h)'); hr.append(hourly(o.hourly)); m.append(hr);
  const live = card('c12', 'Recent orders'); const t = el('table'); const hd = el('tr'); ['#', 'Status', 'Kitchen', 'Deliver to', 'Rider', 'Total', 'Age'].forEach(x => hd.append(el('th', '', x))); t.append(hd);
  s.live.forEach(r => { const tr = el('tr'); const st = el('td'); st.append(pill(r.status.toLowerCase().replace(/_/g, ' '), r.status === 'DELIVERED' ? 'ok' : (r.status === 'REJECTED' || r.status === 'CANCELLED') ? 'bad' : 'warn'));
    [r.id, null, r.kitchen, r.to, r.rider || '–', '₹' + r.total, dur(r.age_s)].forEach((v, i) => tr.append(i === 1 ? st : el('td', '', v))); t.append(tr); });
  if (!s.live.length) t.append(el('tr', '', '')); live.append(t); if (!s.live.length) live.append(el('p', 'muted', 'No orders yet.')); m.append(live);
  const ai = card('c6', 'AI concierge'); const a = s.ai;
  ai.append(kv([['Model', a.model], ['Breaker', a.breaker_open ? 'OPEN' : 'closed'], ['LLM calls', a.calls + ' (' + a.failed + ' failed, ' + a.cache_hits + ' cached)'],
    ['Tokens', a.tokens], ['Latency p50 / p95', (a.p50_ms ?? '–') + ' / ' + (a.p95_ms ?? '–') + ' ms'], ['Readings by', Object.entries(a.reading_sources).map(([k, v]) => k + ' ' + v).join(', ') || '–']]));
  Object.entries(a.eval).forEach(([set, r]) => { ai.append(el('h2', '', 'Eval · ' + set + ' set')); ai.append(bars(Object.entries(r), 100)); }); m.append(ai);
  const tp = card('c6', 'Top dishes & kitchens'); tp.append(bars(s.top_dishes.map(d => [d.name, d.qty]))); tp.append(el('h2', '', 'Kitchens')); tp.append(bars(s.top_kitchens.map(d => [d.name, d.orders]))); m.append(tp);
  const sy = card('c12', 'System'); const y = s.system;
  const checks = Object.entries(h.checks).map(([k, v]) => k + ': ' + (v.ok ? 'ok' : 'FAIL') + (v.detail ? ' (' + v.detail + ')' : '')).join('  ·  ');
  sy.append(kv([['Health checks', checks], ['Uptime', dur(y.uptime_s)], ['Catalogue', y.restaurants + ' kitchens, ' + y.menu_items + ' items'], ['Simulation', y.simulation ? 'on' : 'off'],
    ['Users', s.users.total + ' (' + s.users.with_address + ' with an address)'], ['Database', (y.db_kb ?? '–') + ' KB · last backup ' + dur(y.last_backup_age_s) + ' ago'], ['Python', y.python]])); m.append(sy);
}
load().catch(e => { document.getElementById('m').replaceChildren(el('div', 'card c12', 'Could not load stats (' + e + '). Check the dashboard key in the URL.')); });
setInterval(() => load().catch(() => {}), 5000);
</script></body></html>"""
