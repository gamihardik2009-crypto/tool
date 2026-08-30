"""Maintain X cookies from a persistent Chromium profile on the VPS."""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path


def save_session(context, session_path: Path, status_path: Path) -> bool:
    cookies = context.cookies("https://x.com")
    flat = {item["name"]: item["value"] for item in cookies}
    missing = [name for name in ("auth_token", "ct0") if not flat.get(name)]
    status_path.parent.mkdir(parents=True, exist_ok=True)
    if missing:
        status_path.write_text(json.dumps({"status": "login_required", "missing": missing}, indent=2))
        return False
    temporary = session_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(flat, indent=2), encoding="utf-8")
    os.chmod(temporary, 0o640)
    os.replace(temporary, session_path)
    status_path.write_text(json.dumps({"status": "authenticated", "cookie_count": len(flat)}, indent=2))
    return True


def run(profile: Path, session: Path, status: Path, interval: int) -> None:
    from playwright.sync_api import sync_playwright

    profile.mkdir(parents=True, exist_ok=True)
    session.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(profile), headless=True, channel=os.environ.get("CHROME_CHANNEL") or None,
        )
        page = context.pages[0] if context.pages else context.new_page()
        while True:
            try:
                page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=60_000)
                save_session(context, session, status)
            except Exception as error:
                status.write_text(json.dumps({"status": "error", "error": str(error)[:300]}, indent=2))
            time.sleep(interval)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, default=Path("/var/lib/telegram-x/chrome-profile"))
    parser.add_argument("--session", type=Path, default=Path("/etc/telegram-x/x-session"))
    parser.add_argument("--status", type=Path, default=Path("/var/lib/telegram-x/session-status.json"))
    parser.add_argument("--interval", type=int, default=1800)
    args = parser.parse_args()
    run(args.profile, args.session, args.status, args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
