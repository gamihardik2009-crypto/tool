"""Capture and validate an X session from a real browser over CDP.

The cookie logic mirrors the worker's `session_keeper.py`: collect all cookies
for x.com via `context.cookies()`, require `auth_token` and `ct0`, and write the
flat JSON atomically (temp file + os.replace). We add tweetkit validation on top
so we never save a session that X will already reject.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .browser import wait_for_cdp

REQUIRED_COOKIES = ("auth_token", "ct0")


class LoginTimedOutError(RuntimeError):
    pass


def collect_x_cookies(context) -> dict[str, str]:
    """Return {name: value} for every cookie Chrome holds for x.com."""
    raw = context.cookies("https://x.com")
    return {item["name"]: item["value"] for item in raw}


def required_present(flat: dict[str, str]) -> bool:
    return all(flat.get(name) for name in REQUIRED_COOKIES)


def validate_with_tweetkit(flat: dict[str, str]) -> dict:
    """Confirm the captured session works by asking tweetkit whoami()."""
    from tweetkit_x import TweetKit
    from tweetkit_x.cookie import build_cookie_string

    cookie_string = build_cookie_string(flat)
    client = TweetKit(cookie=cookie_string)
    return client.whoami() or {}


def save_session(flat: dict[str, str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(flat, indent=2), encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def capture_session(port: int, page_url: str = "https://x.com/home",
                    max_wait: float = 300.0, poll: float = 1.5) -> tuple[str, dict]:
    """Connect over CDP, wait for the user to be logged in, return cookies.

    Returns (username_or_user_id, flat_cookies). Raises on timeout.
    """
    from playwright.sync_api import sync_playwright

    if not wait_for_cdp(port):
        raise RuntimeError("Browser did not expose a CDP endpoint in time.")

    deadline = time.monotonic() + max_wait
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(page_url, wait_until="domcontentloaded")

        print(
            "\nA real Chrome window opened. Log into X (x.com) there.\n"
            f"Waiting for an authenticated session (up to {int(max_wait)}s)...\n"
            "When you are logged in this will pick up the session automatically."
        )

        while time.monotonic() < deadline:
            flat = collect_x_cookies(context)
            if required_present(flat):
                identity = validate_with_tweetkit(flat)
                user_id = str(identity.get("user_id") or identity.get("screen_name") or "unknown")
                return user_id, flat
            time.sleep(poll)

        raise LoginTimedOutError(
            "Timed out waiting for an X login. Make sure you logged into x.com in "
            "the window and that no security challenge is blocking the session."
        )


def xlogin(session_path: Path, profile_dir: Path, port: int | None = None,
           max_wait: float = 300.0, browser_path: str | None = None) -> Path:
    """High-level flow: find/provision a real browser, launch + capture + validate.

    `browser_path` optionally overrides auto-detection (e.g. a manually provided
    path when no browser is installed). When omitted, the manager provisions one
    if needed (system browser → cached → download → ask user).
    """
    from .browser import launch_browser
    from .provisioning import resolve_browser

    binary = browser_path if browser_path else resolve_browser(interactive=True)
    profile_dir.mkdir(parents=True, exist_ok=True)
    chosen_port = port or 0
    if chosen_port == 0:
        # Reserve a port, release it, hand it to Chrome. Small race window that's
        # fine in practice; a busy browser is handled below.
        from .browser import find_free_port
        chosen_port = find_free_port()

    process = launch_browser(binary, profile_dir, chosen_port)
    try:
        user_id, flat = capture_session(chosen_port, max_wait=max_wait)
    finally:
        # Leave the profile (so the next login is faster) but drop the process.
        try:
            process.terminate()
        except Exception:
            pass

    save_session(flat, session_path)
    print(f"✅ Authenticated as X user {user_id}")
    print(f"    session saved → {session_path}")
    print(f"    (cookie_count={len(flat)})")
    return session_path