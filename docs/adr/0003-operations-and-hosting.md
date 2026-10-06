# ADR 0003: Operating the bot: one container, in-process ops server, SQLite

Status: accepted (2026-10-06)

## Context
The project must stay online around the clock, cost nothing, and look and behave like something that could be operated by
a team. The first deployment target (Render's free web service) returned 503, and a long-polling bot has no inbound
HTTP traffic for a platform health check to hit. The bot runs on one machine; Telegram allows exactly one poller per token.

## Decision
1. **One container, restart policy `unless-stopped`, Docker volume for state.** Long polling needs no inbound port or tunnel
   and works behind NAT. The image is non-root, read-only, capability-free, with secrets injected at run time.
2. **The bot serves its own ops endpoints** (aiohttp, already a dependency of aiogram) instead of adding a sidecar:
   `/healthz` verifies the dependencies that matter (DB, catalogue, a recent successful Telegram call, a recent simulator tick,
   with a boot grace period) and drives Docker's HEALTHCHECK; `/metrics` speaks Prometheus so a free Prometheus/Grafana can be
   bolted on; the dashboard is off unless `DASHBOARD_KEY` is set. Health and metrics expose no customer data.
3. **Metrics without a library.** Counters, a latency histogram and scrape-time collectors (about 100 lines) cover what we alert
   on; label values are escaped per the exposition format (a test found an initial bug there).
4. **Failure containment at the edge.** An outermost aiogram middleware sets log context, rate-limits per user (token bucket),
   times the handler, and catches anything that escapes, so one bad update never stops polling and the customer always hears back.
5. **SQLite stays.** One writer process, WAL mode, online backups through SQLite's backup API, and a repository-style `db`
   module. Moving to Postgres is a contained change (the module is the only SQL surface besides `orders` and `stats`),
   deliberately deferred: it would add a service to run for no benefit at this scale.
6. **Graceful shutdown.** SIGTERM stops polling, cancels background tasks and closes the HTTP session; `stop_grace_period` is 20 s.

## Consequences
- 24/7 means "as long as the host and Docker are up". A reboot is survived only if Docker Desktop starts with the machine; the
  honest next step for true always-on is an always-free cloud VM running the same compose file (not verified here).
- `docker kill` is treated by Docker as a manual stop; real crashes (non-zero exit) are restarted (demonstrated against the same
  image: 7 restarts in 8 s for a deliberately crashing container).
- One poller per token: running the bot locally while the container is up produces Telegram `Conflict` errors.
- Per-process, in-memory pieces (`LAST_QUERY`, offered "add all" plans, rate-limit buckets, the LLM breaker) reset on restart;
  anything that must survive (orders, couriers, addresses, ratings, events) is in SQLite.
