"""Atomic, non-secret health state for remote inspection."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path


class HealthState:
    def __init__(self, path: Path) -> None:
        self.path = path

    def update(self, status: str, **details: object) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **details,
        }
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)
