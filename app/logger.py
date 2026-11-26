import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import BASE_DIR

LOGS_DIR = BASE_DIR / "logs"
BOT_LOG_FILE = LOGS_DIR / "bot.log"
ERROR_LOG_FILE = LOGS_DIR / "errors.log"


def setup_logging() -> logging.Logger:
    """Configures console + rotating file logging (UTF-8 safe on Windows & Linux servers)."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)

    file_all = RotatingFileHandler(
        BOT_LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_all.setLevel(logging.INFO)
    file_all.setFormatter(fmt)

    file_err = RotatingFileHandler(
        ERROR_LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_err.setLevel(logging.ERROR)
    file_err.setFormatter(fmt)

    root.addHandler(console)
    root.addHandler(file_all)
    root.addHandler(file_err)

    return logging.getLogger("slayd_yasa_bot")


def tail_log(path: Path, lines: int = 25) -> str:
    if not path.exists():
        return "Log fayli hali yaratilmagan."
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(content[-lines:]) if content else "Log bo'sh."
