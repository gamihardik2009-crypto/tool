"""Configuration loaded from a local `.env` file.

Kept deliberately tiny: reads a few simple KEY=VALUE settings. We don't pull in
the python-dotenv library so the project has one dependency only.
"""

from pathlib import Path
from dataclasses import dataclass

BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv() -> None:
    """Load simple `KEY=VALUE` lines from `.env` (if present) into the env."""
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os_setdefault(key.strip(), value.strip().strip('"').strip("'"))


def os_setdefault(key: str, value: str) -> None:
    """Set an env var only if it is not already set. Kept as a tiny helper."""
    import os
    os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    bot_token: str
    chat_id: int | None
    database_path: Path
    log_path: Path
    x_session_path: Path
    health_path: Path


def load_settings() -> Settings:
    _load_dotenv()
    import os

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN is missing. Put your BotFather token in .env"
        )

    raw_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    try:
        chat_id = int(raw_chat_id) if raw_chat_id else None
    except ValueError as error:
        raise ValueError("TELEGRAM_CHAT_ID must be a whole number.") from error

    def _resolve(value: str) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else BASE_DIR / path

    return Settings(
        bot_token=token,
        chat_id=chat_id,
        database_path=_resolve(os.environ.get("DATABASE_PATH", "data/messages.db")),
        log_path=_resolve(os.environ.get("LOG_PATH", "data/collector.log")),
        x_session_path=_resolve(
            os.environ.get("X_SESSION_PATH", "../X-auto-poster/session.json")
        ),
        health_path=_resolve(os.environ.get("HEALTH_PATH", "data/health.json")),
    )
