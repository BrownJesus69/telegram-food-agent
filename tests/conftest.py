from datetime import datetime

import pytest

from foodbot import config, db
from foodbot.services import catalogue, eta

KORAMANGALA = (12.9352, 77.6245)
NOON = datetime(2026, 10, 6, 13, 0, tzinfo=catalogue.IST)         # a Tuesday lunchtime in Bengaluru
LATE = datetime(2026, 10, 7, 3, 30, tzinfo=catalogue.IST)         # 3:30 am
BREAKFAST = datetime(2026, 10, 6, 9, 0, tzinfo=catalogue.IST)


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
    from foodbot import handlers
    from foodbot.concierge import llm as llm_mod
    monkeypatch.setattr(llm_mod, "_default", llm_mod.GroqClient(api_key=""))      # no key: the LLM can never be reached
    handlers.PLANS.clear()
    handlers.LAST_QUERY.clear()          # module-level per-user memory must not leak between tests
    handlers.LAST_SHOWN.clear()
    db.init_db()
    db.upsert_user(1, "Tester")


@pytest.fixture
def at_koramangala():
    """User 1 has a saved delivery address in Koramangala."""
    db.set_location(1, *KORAMANGALA, "Test address")


@pytest.fixture
def bot_env(monkeypatch):
    from tests.bot_harness import ADMIN, BotEnv
    monkeypatch.setattr(config, "ADMIN_IDS", {ADMIN})
    return BotEnv()
