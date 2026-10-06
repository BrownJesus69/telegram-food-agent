import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", encoding="utf-8")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()
MIN_MATCH = int(os.getenv("MIN_MATCH", "70"))
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "foodbot.db"))
DATA_DIR = os.getenv("DATA_DIR", str(BASE_DIR / "data"))

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
