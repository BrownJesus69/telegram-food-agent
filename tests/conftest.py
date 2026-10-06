from datetime import datetime

import pytest

from foodbot import config, db
from foodbot.services import catalogue, eta

KORAMANGALA = (12.9352, 77.6245)
NOON = datetime(2026, 10, 6, 13, 0, tzinfo=catalogue.IST)         # a Tuesday lunchtime in Bengaluru
LATE = datetime(2026, 10, 7, 3, 30, tzinfo=catalogue.IST)         # 3:30 am


@pytest.fixture(scope="session", autouse=True)
def _catalogue_loaded():
    catalogue.load()


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    """Fresh database per test and a frozen clock (lunchtime) so open/closed logic is deterministic."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(catalogue, "now_ist", lambda: NOON)
    monkeypatch.setattr(eta, "now_ist", lambda: NOON)
    # tests must never touch the network or depend on the developer's real keys
    monkeypatch.setattr(config, "GROQ_API_KEY", "")
    monkeypatch.setattr(config, "GEOAPIFY_API_KEY", "")
    db.init_db()
    db.upsert_user(1, "Tester")
    db.set_location(1, *KORAMANGALA, "Test address")
