"""Grounding check: no recommendation may break a hard constraint or reference anything outside the catalogue."""
from __future__ import annotations

from datetime import datetime

from foodbot.concierge import planner
from foodbot.concierge.intent import FoodRequest
from foodbot.services import catalogue


def violations(req: FoodRequest, recs: list[planner.Recommendation], now: datetime | None) -> list[str]:
    bad: list[str] = []
    if len({r.restaurant.id for r in recs}) != len(recs):
        bad.append("two suggestions from the same kitchen")
    for rec in recs:
        rest = rec.restaurant
        if catalogue.RESTAURANTS.get(rest.id) is not rest:
            bad.append(f"{rest.id}: restaurant not in catalogue")
        if not rest.active or not rest.open_at(now):
            bad.append(f"{rest.name}: closed")
        if rec.distance_km > rest.radius_km + 1e-9:
            bad.append(f"{rest.name}: outside delivery radius")
        if not rec.lines:
            bad.append(f"{rest.name}: empty plan")
        for ln in rec.lines:
            it = ln.item
            where = f"{it.name}@{rest.name}"
            if catalogue.ITEMS.get(it.id) is not it:
                bad.append(f"{where}: item not in catalogue")
            if it.restaurant_id != rest.id:
                bad.append(f"{where}: item from another kitchen")
            if not it.available:
                bad.append(f"{where}: out of stock")
            if not 1 <= ln.qty <= planner.MAX_PER_LINE:
                bad.append(f"{where}: quantity {ln.qty}")
            if req.diet and not req.groups and it.diet != req.diet:
                bad.append(f"{where}: diet {it.diet} != {req.diet}")
            for ex in req.exclude:
                if ex == "onion-garlic":
                    if "jain" not in it.tags:
                        bad.append(f"{where}: not Jain-tagged")
                elif ex in it.allergens:
                    bad.append(f"{where}: contains {ex}")
            if req.spice == "hot" and it.spice < 2:
                bad.append(f"{where}: not hot")
            if req.spice == "mild" and it.spice > 1:
                bad.append(f"{where}: not mild")
            if req.tags and not req.dishes and not any(t in it.tags for t in req.tags):
                bad.append(f"{where}: missing tag {req.tags}")
        if req.budget:
            sub = rec.subtotal
            if req.budget_scope == "item" and any(ln.item.price > req.budget for ln in rec.lines):
                bad.append(f"{rest.name}: item over budget")
            if req.budget_scope == "per_person" and sub > req.budget * max(req.servings, 1):
                bad.append(f"{rest.name}: over per-person budget")
            if req.budget_scope == "total" and sub > req.budget:
                bad.append(f"{rest.name}: over total budget")
    return bad
