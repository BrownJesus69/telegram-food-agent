"""Simulated delivery partner: a generated rider persona and a believable route from kitchen to doorstep.

Everything is a pure function of the order id and coordinates, so the position of a rider is a function of elapsed time
alone. That makes the simulation restart-safe (no in-memory state) and trivially testable.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from foodbot.services.distance import haversine_km

FIRST = ("Manjunath", "Ravi", "Suresh", "Prakash", "Mahesh", "Lokesh", "Kiran", "Naveen", "Venkatesh", "Santosh", "Imran", "Arif",
         "Mohan", "Basavaraj", "Shivu", "Raju", "Harish", "Dinesh", "Girish", "Yogesh", "Anil", "Sunil", "Faiz", "Karthik")
LAST_INITIAL = "BCDGHJKMNPRSTV"
VEHICLES = ("Honda Activa", "TVS Jupiter", "Hero Splendor", "Bajaj Pulsar", "Ather 450 (electric)", "Suzuki Access", "TVS Ntorq")
PLATE_LETTERS = "ABCDEFGHJKLMNPRSTUVWXYZ"


@dataclass(frozen=True)
class Persona:
    name: str
    vehicle: str
    phone: str          # masked, display only
    rating: float


def persona_for(order_id: int) -> Persona:
    rng = random.Random(f"rider:{order_id}")
    name = f"{rng.choice(FIRST)} {rng.choice(LAST_INITIAL)}."
    plate = f"KA {rng.randint(1, 59):02d} {rng.choice(PLATE_LETTERS)}{rng.choice(PLATE_LETTERS)} {rng.randint(1000, 9999)}"
    phone = f"+91 {rng.choice('6789')}{rng.randint(0, 9)}••• ••{rng.randint(10, 99)}"
    return Persona(name, f"{rng.choice(VEHICLES)} · {plate}", phone, round(rng.uniform(4.5, 4.9), 1))


Point = tuple[float, float]


def build_route(start: Point, end: Point, seed: int | str) -> list[Point]:
    """A city-like path: one turn at a street corner, slightly wobbly legs instead of a straight line."""
    rng = random.Random(f"route:{seed}")
    elbow = (end[0], start[1]) if rng.random() < 0.5 else (start[0], end[1])
    pts: list[Point] = [start]
    for a, b in ((start, elbow), (elbow, end)):
        for frac in (1 / 3, 2 / 3):
            lat = a[0] + (b[0] - a[0]) * frac + rng.uniform(-0.0004, 0.0004)
            lon = a[1] + (b[1] - a[1]) * frac + rng.uniform(-0.0004, 0.0004)
            pts.append((lat, lon))
        pts.append(b)
    return pts


def route_length_km(route: list[Point]) -> float:
    return sum(haversine_km(*a, *b) for a, b in zip(route, route[1:], strict=False))


def position_at(route: list[Point], progress: float) -> Point:
    """Where the rider is after `progress` (0..1) of the trip; eases in and out like a real rider at junctions."""
    p = min(max(progress, 0.0), 1.0)
    p = p * p * (3 - 2 * p)
    total = route_length_km(route)
    if total == 0:
        return route[-1]
    target = p * total
    walked = 0.0
    for a, b in zip(route, route[1:], strict=False):
        seg = haversine_km(*a, *b)
        if walked + seg >= target and seg > 0:
            f = (target - walked) / seg
            return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
        walked += seg
    return route[-1]
