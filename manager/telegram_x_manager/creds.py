"""Local credential storage for the manager.

Holds the Telegram bot token + optional chat id. Saved in the manager's config
dir with 0600 perms. The X session and SSH private key are stored separately.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from . import config


def load(path: Path | None = None) -> dict:
    path = path or config.creds_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(token: str, chat_id: str, path: Path | None = None) -> None:
    path = path or config.creds_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"telegram_bot_token": token, "chat_id": chat_id},
                               indent=2), encoding="utf-8")
    os.chmod(path, 0o600)


def bot_token(path: Path | None = None) -> str:
    return (load(path) or {}).get("telegram_bot_token", "").strip()


def chat_id(path: Path | None = None) -> str:
    return (load(path) or {}).get("chat_id", "").strip()