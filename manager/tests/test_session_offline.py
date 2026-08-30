"""Offline test of the cookie capture/validation helpers used by `xlogin`.

Injects synthetic but structurally-correct x.com cookies over CDP, then runs the
same collection + required-check + atomic-save logic as production.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from telegram_x_manager.browser import detect_browser_binary, find_free_port, wait_for_cdp
from telegram_x_manager.session import collect_x_cookies, required_present, save_session

BINARY = detect_browser_binary()
PORT = find_free_port()
PROFILE = tempfile.mkdtemp(prefix="tzx-session-test-")
OUT = Path(tempfile.mkdtemp(prefix="tzx-out-")) / "session.json"

proc = subprocess.Popen(
    [BINARY, f"--remote-debugging-port={PORT}", f"--user-data-dir={PROFILE}",
     "--headless=new", "about:blank"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
try:
    if not wait_for_cdp(PORT, timeout=20):
        raise SystemExit("CDP not up")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{PORT}")
        context = browser.contexts[0]
        context.add_cookies([
            {"name": "auth_token", "value": "fake_auth_token", "domain": ".x.com", "path": "/"},
            {"name": "ct0", "value": "fake_ct0", "domain": ".x.com", "path": "/"},
            {"name": "twid", "value": "u=123", "domain": ".x.com", "path": "/"},
        ])
        flat = collect_x_cookies(context)
        assert required_present(flat), "required check failed"
        save_session(flat, OUT)
        browser.close()
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()

saved = json.loads(OUT.read_text())
assert saved["auth_token"] == "fake_auth_token"
assert saved["ct0"] == "fake_ct0"
assert (OUT.parent / "session.json.tmp").exists() is False, "temp file not cleaned up"
print("OK: collected", len(saved), "cookies; auth_token+ct0 present; atomic save worked")
print("session keys:", sorted(saved.keys()))