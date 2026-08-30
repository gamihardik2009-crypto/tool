"""Quick CDP plumbing check: launch REAL chrome headless, attach via sync CDP,
confirm the page reports navigator.webdriver === false, and read cookies.

This is only for validating the tool machinery in this headless environment.
Production `xlogin` runs the browser headful so the user can log in.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from telegram_x_manager.browser import detect_browser_binary, find_free_port, wait_for_cdp

BINARY = detect_browser_binary()
PORT = find_free_port()
PROFILE = tempfile.mkdtemp(prefix="tzx-cdp-test-")

args = [
    BINARY,
    f"--remote-debugging-port={PORT}",
    f"--user-data-dir={PROFILE}",
    "--headless=new",
    "about:blank",
]
proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    if not wait_for_cdp(PORT, timeout=20):
        print("FAIL: CDP endpoint never came up")
        raise SystemExit(1)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{PORT}")
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else context.new_page()
        webdriver = page.evaluate("navigator.webdriver")
        print(f"navigator.webdriver = {webdriver}")
        print("CDP cookie count:", len(context.cookies("https://x.com")))
        browser.close()
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()

if not isinstance(webdriver, bool) or webdriver is not False:
    print("FAIL: webdriver flag not false")
    raise SystemExit(1)
print("OK: real Chrome + connect_over_cdp works; webdriver=false")