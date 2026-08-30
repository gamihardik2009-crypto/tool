"""Local activity history for the manager.

Keeps the last N actions (with timestamp + ok/detail) so the `health` screen can
show the user what the tool has been doing recently. Stored as a simple JSON log
in the manager's config dir.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from . import config

DEFAULT_LIMIT = 10


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_history(path: Path | None = None) -> list[dict]:
    path = path or config.activity_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (OSError, ValueError):
        pass
    return []


def _clean(value: object) -> object:
    """Strip secrets from detail lines before they reach the log."""
    if isinstance(value, str):
        for redacted in ("token", "cookie", "authorization", "password"):
            if redacted in value.lower():
                return "[redacted]"
        if len(value) > 300:
            return value[:300] + "…"
    return value


def record(action: str, ok: bool, detail: str = "", limit: int = DEFAULT_LIMIT,
            path: Path | None = None) -> None:
    """Append one activity record, trimming to the newest `limit` entries."""
    path = path or config.activity_path()
    history = load_history(path)
    history.append({
        "ts": _now(),
        "action": action,
        "ok": bool(ok),
        "detail": _clean(detail),
    })
    history = history[-limit:]
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(history, indent=2), encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def history(limit: int = DEFAULT_LIMIT, path: Path | None = None) -> list[dict]:
    return load_history(path)[-limit:]