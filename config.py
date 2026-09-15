import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        logging.critical("Missing required env var: %s", name)
        sys.exit(1)
    return value


BOT_TOKEN: str = _require("BOT_TOKEN")
GEMINI_API_KEY: str = _require("GEMINI_API_KEY")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
FIREBASE_CREDENTIALS_PATH: str = os.getenv(
    "FIREBASE_CREDENTIALS_PATH", "firebase_credentials.json"
)
FIREBASE_CREDENTIALS_JSON: str | None = os.getenv("FIREBASE_CREDENTIALS_JSON")
DEFAULT_TIMEZONE: str = os.getenv("DEFAULT_TIMEZONE", "Asia/Tashkent")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
