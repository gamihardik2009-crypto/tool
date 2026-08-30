"""Launch a *real* Chromium-family browser with a CDP debugging port.

Why not Playwright-launched browsers: Playwright's *launched* browser sets
`--enable-automation` and makes `navigator.webdriver === true`, which X and
Google fingerprint as bot/insecure. By launching the user's real Chrome/Edge/
Chromium ourselves (without those flags) and then merely *connecting* to it
over CDP, the session looks like a normal human browser.

We only need Playwright's sync API as a lightweight CDP client
(`connect_over_cdp`), never its launcher.
"""
from __future__ import annotations

import platform
import shutil
import socket
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen


class BrowserNotFoundError(RuntimeError):
    pass


def find_free_port(host: str = "127.0.0.1") -> int:
    """Ask the OS for a currently free TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


def _candidate_binaries() -> list[str]:
    if platform.system() == "Windows":
        return [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Users\%USERNAME%\AppData\Local\Google\Chrome\Application\chrome.exe",
        ]
    if platform.system() == "Darwin":
        return [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    # Linux
    return [
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "microsoft-edge",
        "microsoft-edge-stable",
        "brave-browser",
    ]


def detect_browser_binary() -> str:
    """Find a real Chromium-family browser on this machine, portable."""
    for candidate in _candidate_binaries():
        resolved = shutil.which(candidate) if not candidate.startswith(("/", "C:")) else candidate
        if resolved:
            return resolved
        if Path(candidate).expanduser().exists():
            return str(Path(candidate).expanduser())
    raise BrowserNotFoundError(
        "Could not find a real Chrome/Chromium/Edge browser. Install one, or "
        "be sure your browser is in PATH, then retry `xlogin`."
    )


def launch_browser(binary: str, profile_dir: Path, port: int) -> subprocess.Popen:
    """Start the real browser headful with a dedicated profile and CDP port."""
    args = [
        binary,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--no-service-autorun",
        "https://x.com/home",
    ]
    return subprocess.Popen(args)


def wait_for_cdp(port: int, timeout: float = 60.0) -> bool:
    """Poll the CDP HTTP endpoint until the browser is ready to accept clients."""
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/json/version"
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=2):
                return True
        except Exception:
            time.sleep(0.5)
    return False