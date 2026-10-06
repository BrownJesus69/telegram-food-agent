import pytest

from foodbot import db, geo, orders, parser
from foodbot.services import catalogue
from foodbot.services.search import closed_matches, search_items

from .conftest import KORAMANGALA, LATE, NOON


def _orderable(query="biryani", **kw):
    """First search hit whose restaurant lets a 2-item cart through (so tests don't hard-code ids)."""
    for r in search_items(query, *KORAMANGALA, limit=50, **kw):
        if r.item.price * 2 >= r.restaurant.min_order:
            return r
    raise AssertionError(f"no orderable hit for {query!r}")


def test_parse_basic():
    q = parser.parse("I am hungry, I want Shawarma under 200")
    assert (q.dish, q.budget, q.qty) == ("shawarma", 200, 1)


def test_parse_qty_and_rupee():
    q = parser.parse("2 chicken shawarma below rs 300")
    assert (q.dish, q.budget, q.qty) == ("chicken shawarma", 300, 2)


def test_parse_diet():
    assert parser.parse("pure veg burger").diet == "veg"
    assert parser.parse("non veg roll").diet == "non_veg"


def test_haversine():
    assert geo.haversine_km(*KORAMANGALA, *KORAMANGALA) == pytest.approx(0, abs=1e-6)
    assert 3 < geo.haversine_km(12.9352, 77.6245, 12.9784, 77.6408) < 7


def test_search_respects_budget_stock_radius_and_hours():
    res = search_items("biryani", *KORAMANGALA, budget=300, limit=20, now=NOON)
    assert res, "Koramangala at lunchtime must have biryani under 300"
    for r in res:
        assert r.item.price <= 300
        assert r.item.available
        assert r.restaurant.open_at(NOON)
        assert r.distance_km <= r.restaurant.radius_km
    assert search_items("sushi platter of unicorn", *KORAMANGALA, now=NOON) == []


def test_search_one_result_per_restaurant_and_sorted():
    res = search_items("biryani", *KORAMANGALA, limit=30, now=NOON)
    assert len({r.restaurant.id for r in res}) == len(res)
    assert [r.score for r in res] == sorted((r.score for r in res), reverse=True)


def test_search_diet_filters():
    veg = search_items("biryani", *KORAMANGALA, diet="veg", limit=20, now=NOON)
    assert veg and all(r.item.diet == "veg" for r in veg)
    nonveg = search_items("biryani", *KORAMANGALA, diet="non_veg", limit=20, now=NOON)
    assert nonveg and all(r.item.diet in ("nonveg", "egg") for r in nonveg)


def test_search_matches_local_names_and_typos():
    assert search_items("benne dosa", *KORAMANGALA, now=NOON, include_closed=True)
    assert search_items("masala dose", *KORAMANGALA, now=NOON, include_closed=True)   # Kannada-style spelling
    assert search_items("filter kaapi", *KORAMANGALA, now=NOON, include_closed=True)


def test_closed_restaurants_are_hidden_and_reported():
    # at 3:30 am almost nothing is open; a breakfast dish must not come back as orderable
    open_now = search_items("idli", *KORAMANGALA, now=LATE, limit=50)
    assert all(r.restaurant.open_at(LATE) for r in open_now)
    assert closed_matches("idli", *KORAMANGALA, now=LATE)


def test_order_flow_idempotent():
    hit = _orderable("biryani")
    other = next(r for r in search_items("dosa", *KORAMANGALA, limit=50, now=NOON) if r.restaurant.id != hit.restaurant.id)
    assert orders.add_item(1, hit.item.id, 2) == "ok"
    assert orders.add_item(1, other.item.id, 1) == "conflict"
    s = orders.cart_summary(1)
    assert s["subtotal"] == hit.item.price * 2
    assert s["total"] == s["subtotal"] + hit.restaurant.delivery_fee
    assert not s["issues"], s["issues"]
    db.set_field(1, pending_key="abc123")
    oid, new = orders.create_order(1, "abc123")
    assert new
    oid2, new2 = orders.create_order(1, "abc123")
    assert oid2 == oid and not new2
    assert orders.cart_summary(1) is None
    order, items = orders.get_order(oid)
    assert order["status"] == "PENDING" and items[0]["quantity"] == 2


def test_expired_checkout_rejected():
    orders.add_item(1, _orderable().item.id, 2)
    with pytest.raises(orders.OrderError):
        orders.create_order(1, "wrong")


def test_status_transitions():
    orders.add_item(1, _orderable().item.id, 2)
    db.set_field(1, pending_key="k1")
    oid, _ = orders.create_order(1, "k1")
    with pytest.raises(orders.OrderError):
        orders.transition(oid, "DELIVERED")
    for s in ("ACCEPTED", "PREPARING", "OUT_FOR_DELIVERY", "DELIVERED"):
        orders.transition(oid, s)
    with pytest.raises(orders.OrderError):
        orders.transition(oid, "CANCELLED")


def test_cart_blocks_closed_restaurant(monkeypatch):
    hit = _orderable()
    orders.add_item(1, hit.item.id, 2)
    monkeypatch.setattr(catalogue, "now_ist", lambda: LATE)
    if hit.restaurant.open_at(LATE):
        pytest.skip("restaurant happens to be open at 3:30 am")
    assert any("closed" in i for i in orders.cart_summary(1)["issues"])


def test_cart_blocks_outside_delivery_radius():
    hit = _orderable()
    orders.add_item(1, hit.item.id, 2)
    db.set_location(1, 13.1189, 77.7267, "far away")      # north-east edge of the city
    assert any("delivery area" in i for i in orders.cart_summary(1)["issues"])


def test_minimum_order_enforced():
    r = next(r for r in search_items("biryani", *KORAMANGALA, limit=200, now=NOON) if r.restaurant.min_order > r.item.price)
    orders.add_item(1, r.item.id, 1)
    assert any("minimum order" in i for i in orders.cart_summary(1)["issues"])
