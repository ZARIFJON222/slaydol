import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN .env faylida topilmadi!")

_raw_admins = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: set[int] = {
    int(x.strip()) for x in _raw_admins.split(",") if x.strip().isdigit()
}

_cred_raw = os.getenv("FIREBASE_CREDENTIALS", "firebase-credentials.json").strip()
FIREBASE_CREDENTIALS: Path = (
    Path(_cred_raw) if Path(_cred_raw).is_absolute() else BASE_DIR / _cred_raw
)

_raw_keys = os.getenv("GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEY", "")
GEMINI_API_KEYS: list[str] = [k.strip() for k in _raw_keys.split(",") if k.strip()]
GEMINI_API_KEY: str = GEMINI_API_KEYS[0] if GEMINI_API_KEYS else ""

GENERATED_DIR: Path = BASE_DIR / "generated"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)

WEBAPP_URL: str = os.getenv("WEBAPP_URL", "").strip()
WEBAPP_PORT: int = int(os.getenv("WEBAPP_PORT", "8080"))
WEBAPP_DIR: Path = BASE_DIR / "webapp"
