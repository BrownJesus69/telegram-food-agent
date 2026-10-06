"""Tiny Prometheus-style metrics (no dependency): counters, gauges, histograms and scrape-time collectors."""
from __future__ import annotations

import time
from collections.abc import Callable, Iterable

LATENCY_BUCKETS = (0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)


def _escape(value) -> str:
    """Prometheus exposition escaping: backslash, double quote and newline."""
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _fmt_labels(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    return "{" + ",".join(f'{k}="{_escape(v)}"' for k, v in labels) + "}"


class Counter:
    def __init__(self, name: str, help_: str):
        self.name, self.help = name, help_
        self.values: dict[tuple, float] = {}

    def inc(self, amount: float = 1, **labels):
        key = tuple(sorted(labels.items()))
        self.values[key] = self.values.get(key, 0) + amount

    def get(self, **labels) -> float:
        return self.values.get(tuple(sorted(labels.items())), 0)

    def total(self) -> float:
        return sum(self.values.values())

    def render(self) -> Iterable[str]:
        yield f"# HELP {self.name} {self.help}"
        yield f"# TYPE {self.name} counter"
        for key, v in sorted(self.values.items()) or [((), 0)]:
            yield f"{self.name}{_fmt_labels(key)} {v:g}"


class Histogram:
    def __init__(self, name: str, help_: str, buckets=LATENCY_BUCKETS):
        self.name, self.help, self.buckets = name, help_, buckets
        self.counts = [0] * len(buckets)
        self.sum = 0.0
        self.n = 0

    def observe(self, value: float):
        self.n += 1
        self.sum += value
        for i, b in enumerate(self.buckets):
            if value <= b:
                self.counts[i] += 1

    def quantile(self, q: float) -> float | None:
        """Bucket-resolution quantile (upper bound of the bucket containing it)."""
        if not self.n:
            return None
        target = q * self.n
        for b, c in zip(self.buckets, self.counts, strict=True):
            if c >= target:
                return b
        return float("inf")

    def render(self) -> Iterable[str]:
        yield f"# HELP {self.name} {self.help}"
        yield f"# TYPE {self.name} histogram"
        for b, c in zip(self.buckets, self.counts, strict=True):
            yield f'{self.name}_bucket{{le="{b}"}} {c}'
        yield f'{self.name}_bucket{{le="+Inf"}} {self.n}'
        yield f"{self.name}_sum {self.sum:.6f}"
        yield f"{self.name}_count {self.n}"


class Registry:
    def __init__(self):
        self.metrics: list = []
        self.collectors: list[Callable[[], Iterable[str]]] = []

    def counter(self, name, help_):
        m = Counter(name, help_)
        self.metrics.append(m)
        return m

    def histogram(self, name, help_, buckets=LATENCY_BUCKETS):
        m = Histogram(name, help_, buckets)
        self.metrics.append(m)
        return m

    def collector(self, fn):
        self.collectors.append(fn)
        return fn

    def render(self) -> str:
        lines: list[str] = []
        for m in self.metrics:
            lines.extend(m.render())
        for fn in self.collectors:
            try:
                lines.extend(fn())
            except Exception as e:                         # a broken collector must not break the scrape
                lines.append(f"# collector {getattr(fn, '__name__', '?')} failed: {type(e).__name__}")
        return "\n".join(lines) + "\n"


def gauge_lines(name: str, help_: str, value: float | None, **labels) -> list[str]:
    if value is None:
        return []
    return [f"# HELP {name} {help_}", f"# TYPE {name} gauge", f"{name}{_fmt_labels(tuple(sorted(labels.items())))} {value:g}"]


REGISTRY = Registry()
UPDATES = REGISTRY.counter("foodbot_updates_total", "Telegram updates handled, by kind")
UPDATE_ERRORS = REGISTRY.counter("foodbot_update_errors_total", "Updates whose handler raised")
UPDATE_SECONDS = REGISTRY.histogram("foodbot_update_seconds", "Handler latency per update")
RATE_LIMITED = REGISTRY.counter("foodbot_rate_limited_total", "Updates dropped by the per-user rate limiter")
ORDERS = REGISTRY.counter("foodbot_order_transitions_total", "Order state transitions, by new status")
SEARCHES = REGISTRY.counter("foodbot_searches_total", "Concierge searches, by outcome and reading source")
STARTED_AT = time.time()
