"""Record live LLM replies for the golden set into the production model's cassette (evals/cassettes/) (resumable; respects Groq's free-tier limits).

    python -m evals.record

Needs GROQ_API_KEY. About 1,100 tokens per call against an 8,000 tokens/minute limit, so it paces itself and retries
after rate limits. Already-recorded messages are skipped, so it can be interrupted and re-run.
"""
from __future__ import annotations

import asyncio
import logging
import time

from evals.run import CASSETTE, load_golden
from foodbot.concierge.llm import Cassette, GroqClient

PAUSE = 8.5          # seconds between calls: ~7 calls/minute stays under the token limit
log = logging.getLogger("record")


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    cassette = Cassette(CASSETTE)
    client = GroqClient(cassette=cassette, record=True, timeout=20)
    if not client.api_key:
        raise SystemExit("GROQ_API_KEY is not set")
    every = load_golden("both")
    todo = [c for c in every if cassette.get(c["text"]) is None]
    log.info("%d of %d messages still to record", len(todo), len(every))
    for i, case in enumerate(todo, 1):
        for attempt in range(1, 5):
            got = await client.interpret(case["text"])
            if got:
                break
            wait = max(client.breaker.open_until - time.monotonic(), 0) + 2
            log.info("  retry %d for %r after %.0fs", attempt, case["text"], wait)
            await asyncio.sleep(min(wait, 90))
            client.breaker.open_until, client.breaker.failures = 0.0, 0
        else:
            log.warning("gave up on %r", case["text"])
        log.info("[%d/%d] %s -> %s", i, len(todo), case["id"], got.describe() if got else None)
        await asyncio.sleep(PAUSE)
    log.info("done; stats %s", {k: v for k, v in client.stats.items() if k != "latency_ms"})


if __name__ == "__main__":
    asyncio.run(main())
