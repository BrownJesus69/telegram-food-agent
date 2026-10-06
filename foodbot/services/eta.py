"""Delivery-time estimate: kitchen prep + traffic-aware travel time.

Bengaluru roads are slow, so the base pace is 4.5 min/km, stretched during the morning and
evening peaks. This is a catalogue estimate, not live tracking.
"""
from __future__ import annotations

from datetime import datetime

from foodbot.services.catalogue import IST, now_ist

BASE_MIN_PER_KM = 4.5
MIN_TRAVEL_MIN = 8
BUFFER_MIN = 10

# (start minute, end minute, multiplier) in IST
_PEAKS = ((8 * 60, 10 * 60 + 30, 1.35), (12 * 60 + 30, 14 * 60, 1.1), (17 * 60 + 30, 21 * 60, 1.5))


def traffic_factor(now: datetime | None = None) -> float:
    now = (now or now_ist()).astimezone(IST)
    m = now.hour * 60 + now.minute
    for a, b, f in _PEAKS:
        if a <= m < b:
            return f
    return 1.0


def estimate_eta(distance_km: float, prep_minutes: float = 20, now: datetime | None = None) -> tuple[int, int]:
    """Return (min, max) minutes from order acceptance to doorstep."""
    travel = max(MIN_TRAVEL_MIN, round(float(distance_km or 0) * BASE_MIN_PER_KM * traffic_factor(now)))
    lo = int(round(float(prep_minutes or 20) + travel))
    return lo, lo + BUFFER_MIN
