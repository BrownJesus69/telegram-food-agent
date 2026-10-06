import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", encoding="utf-8")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip()
GROQ_STT_MODEL = os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo").strip()
MIN_MATCH = int(os.getenv("MIN_MATCH", "70"))
MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", "5"))
# DB_PATH is canonical; DATABASE_PATH is accepted because older .env files used it.
DB_PATH = os.getenv("DB_PATH") or os.getenv("DATABASE_PATH") or str(BASE_DIR / "foodbot.db")
DATA_DIR = os.getenv("DATA_DIR", str(BASE_DIR / "seed_data"))

# --- delivery simulation (kitchen auto-accepts, a generated rider rides a live-location route) --------------
SIMULATE_DELIVERY = os.getenv("SIMULATE_DELIVERY", "1").strip().lower() in {"1", "true", "yes", "on"}
SIM_SECONDS_PER_MINUTE = float(os.getenv("SIM_SECONDS_PER_MINUTE", "1.5"))   # demo clock: 1 catalogue minute = 1.5 real seconds
SIM_ACCEPT_SECONDS = float(os.getenv("SIM_ACCEPT_SECONDS", "8"))             # kitchen "reads" the order for about this long
SIM_REJECT_RATE = float(os.getenv("SIM_REJECT_RATE", "0"))                   # chance a simulated kitchen declines an order
SIM_TICK_SECONDS = float(os.getenv("SIM_TICK_SECONDS", "2"))
SIM_LIVE_EDIT_SECONDS = float(os.getenv("SIM_LIVE_EDIT_SECONDS", "5"))       # how often the live location moves

ADMIN_IDS = {
    int(x)
    for x in os.getenv("ADMIN_CHAT_ID", "").replace(" ", "").split(",")
    if x.lstrip("-").isdigit()
}


def validate():
    missing = []
    if not BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not ADMIN_IDS:
        missing.append("ADMIN_CHAT_ID (numeric)")
    if missing:
        raise RuntimeError("Missing in .env: " + ", ".join(missing))
