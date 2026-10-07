import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", encoding="utf-8")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY", "").strip()
# Chosen by measurement (evals/BAKEOFF.md): best held-out accuracy of the free Groq models at ~40% of the tokens per call.
DEFAULT_GROQ_MODEL = "qwen/qwen3.8-27b"
GROQ_MODEL = os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL).strip()
GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", DEFAULT_GROQ_MODEL).strip()      # must accept image_url content (the gpt-oss models do not)
PHOTO_BURST = float(os.getenv("PHOTO_BURST", "3"))                           # per-user photo reads in a burst ...
PHOTO_PER_SECOND = float(os.getenv("PHOTO_PER_SECOND", "0.05"))              # ... refilled at one per 20 s (each read costs ~2,000 free-tier tokens)
PHOTO_GLOBAL_BURST = float(os.getenv("PHOTO_GLOBAL_BURST", "3"))             # across all customers: about 3 reads a minute keeps text under the 8k tokens/min cap
PHOTO_GLOBAL_PER_SECOND = float(os.getenv("PHOTO_GLOBAL_PER_SECOND", "0.05"))
GROQ_STT_MODEL =os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo").strip()
MIN_MATCH = int(os.getenv("MIN_MATCH", "70"))
MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", "5"))
# Public https URL of the map-picker Mini App (miniapp/index.html, e.g. on GitHub Pages). Empty = the "Pick on map" button is not offered.
MINIAPP_URL = os.getenv("MINIAPP_URL", "").strip()
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

# --- operations -----------------------------------------------------------------------------------------
LOG_FORMAT = os.getenv("LOG_FORMAT", "text").strip().lower()                 # "json" in containers
OPS_HOST = os.getenv("OPS_HOST", "127.0.0.1").strip()                        # health/metrics/dashboard server
OPS_PORT = int(os.getenv("OPS_PORT", "8080"))
DASHBOARD_KEY = os.getenv("DASHBOARD_KEY", "").strip()                       # empty = dashboard disabled (health + metrics stay on)
THROTTLE_BURST = float(os.getenv("THROTTLE_BURST", "10"))                    # per-user burst of messages ...
THROTTLE_PER_SECOND = float(os.getenv("THROTTLE_PER_SECOND", "0.5"))         # ... refilled at this rate
BACKUP_DIR = os.getenv("BACKUP_DIR", str(BASE_DIR / "backups"))
BACKUP_EVERY_HOURS = float(os.getenv("BACKUP_EVERY_HOURS", "6"))

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
