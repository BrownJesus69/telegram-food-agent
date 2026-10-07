# Load test: 50 customers at once

Run: 2026-10-07 08:15 on Windows AMD64, Python 3.12.10, one process, SQLite (WAL), Telegram HTTP replaced by an in-memory recorder (no network latency included).

**50 concurrent customers, 423 updates in 5.0 s = 84 updates/s; 33 orders placed (33/50 journeys completed).**

| Step | n | p50 | p95 | p99 | max |
|---|---|---|---|---|---|
| /start | 50 | 295 ms | 536 ms | 555 ms | 555 ms |
| share a pin | 50 | 473 ms | 544 ms | 551 ms | 551 ms |
| name the address | 50 | 522 ms | 611 ms | 617 ms | 617 ms |
| search in plain words | 50 | 1223 ms | 1551 ms | 1578 ms | 1578 ms |
| add to cart | 42 | 857 ms | 1536 ms | 1688 ms | 1688 ms |
| checkout | 42 | 339 ms | 389 ms | 391 ms | 391 ms |
| change quantity | 64 | 269 ms | 313 ms | 314 ms | 314 ms |
| skip landmark | 42 | 281 ms | 337 ms | 347 ms | 347 ms |
| confirm order | 33 | 279 ms | 314 ms | 319 ms | 319 ms |

Journeys that did not reach an order (the search found nothing orderable for the shared pin, or the cart was blocked by a kitchen rule such as its minimum order):
- 'masala dosa and filter coffee': cart blocked: Padmavathi Tiffin Room has a minimum order of ₹149 (your items: ₹135). (x9)
- 'paneer tikka no onion garlic': no orderable result (x8)

All updates together: p50 378 ms, p95 1351 ms, p99 1551 ms.

How to read it: all customers start together, so each update waits behind the others' (single event loop, synchronous SQLite). The per-step latency is therefore a worst case for 'N people tapping at the same instant'; a steady 50 users would see roughly the p50.
