import pytest
from services import catalogue
import db
import geo
import orders
import parser
import search

KORAMANGALA = (12.9352, 77.6245)


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))
    db.init_db()
    catalogue.load()
    db.upsert_user(1, "Tester")
    db.set_location(1, *KORAMANGALA, "Test address")


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


def test_search_budget_and_unavailable():
    res = search.search(parser.parse("shawarma under 200"), *KORAMANGALA)
    assert res and all(r["item"].price <= 200 for r in res)
    assert all(r["item"].available for r in res)
    none = search.search(parser.parse("sushi"), *KORAMANGALA)
    assert none == []


def test_search_veg_filter():
    res = search.search(parser.parse("veg burger"), *KORAMANGALA)
    assert res and all(r["item"].veg for r in res)


def test_order_flow_idempotent():
    assert orders.add_item(1, "I001", 2) == "ok"
    assert orders.add_item(1, "I004", 1) == "conflict"
    s = orders.cart_summary(1)
    assert s["subtotal"] == 298 and s["total"] == 328 and not s["issues"]
    db.set_field(1, pending_key="abc123")
    oid, new = orders.create_order(1, "abc123")
    assert new
    oid2, new2 = orders.create_order(1, "abc123")
    assert oid2 == oid and not new2
    assert orders.cart_summary(1) is None
    order, items = orders.get_order(oid)
    assert order["status"] == "PENDING" and items[0]["quantity"] == 2


def test_expired_checkout_rejected():
    orders.add_item(1, "I001", 1)
    with pytest.raises(orders.OrderError):
        orders.create_order(1, "wrong")


def test_status_transitions():
    orders.add_item(1, "I001", 1)
    db.set_field(1, pending_key="k1")
    oid, _ = orders.create_order(1, "k1")
    with pytest.raises(orders.OrderError):
        orders.transition(oid, "DELIVERED")
    for s in ("ACCEPTED", "PREPARING", "OUT_FOR_DELIVERY", "DELIVERED"):
        orders.transition(oid, s)
    with pytest.raises(orders.OrderError):
        orders.transition(oid, "CANCELLED")
