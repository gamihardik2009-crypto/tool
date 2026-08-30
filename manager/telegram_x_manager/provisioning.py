"""Browser provisioning: make sure the manager always has a browser to use.

Resolution order (first hit wins):

1. A real Chromium-family browser already on the OS (Chrome/Edge/Brave/Chromium).
2. A browser already downloaded into the tool's own cache dir (a previous run on
   a browser-less machine).
3. Download a genuine **Chrome for Testing** into the tool's cache dir.
4. Ask the user for a browser path.

Why downloading is safe: anti-bot detection comes from the *launch flags*, not
the binary's origin. Any of these browsers is launched by us via `subprocess`
with its OWN profile and `--remote-debugging-port`, WITHOUT `--enable-automation`,
so `navigator.webdriver` stays `false`. We never use Playwright's launcher, so we
never add those automation flags — the browser looks like a normal human browser.
"""
from __future__ import annotations

import hashlib
import json
import platform
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

from . import config
from .browser import BrowserNotFoundError, detect_browser_binary

CHROME_FOR_TESTING_METADATA = (
    "https://googlechromelabs.github.io/chrome-for-testing/"
    "last-known-good-versions-with-downloads.json"
)


def _platform_key() -> str:
    machine = platform.machine().lower()
    system = platform.system()
    if system == "Windows":
        return "win64"
    if system == "Darwin":
        return "mac-arm64" if machine in ("arm64", "aarch64") else "mac-x64"
    # Linux
    return "linux64" if machine in ("x86_64", "amd64") else "linux64"


def _binary_name_for(plat: str) -> str:
    return "chrome.exe" if plat == "win64" else "chrome"


def _binary_path_in_extracted(plat: str, extract_root: Path) -> Path:
    if plat == "win64":
        return extract_root / "chrome-win64" / "chrome.exe"
    if plat == "mac-arm64":
        return (
            extract_root / "chrome-mac-arm64"
            / "Google Chrome for Testing.app" / "Contents" / "MacOS"
            / "Google Chrome for Testing"
        )
    if plat == "mac-x64":
        return (
            extract_root / "chrome-mac-x64"
            / "Google Chrome for Testing.app" / "Contents" / "MacOS"
            / "Google Chrome for Testing"
        )
    return extract_root / "chrome-linux64" / "chrome"


def cached_browser_binary() -> Path | None:
    """Return a previously downloaded browser in our cache, or None."""
    plat = _platform_key()
    expected = _binary_name_for(plat)
    for candidate in sorted(config.browser_cache_dir().glob("**/*")):
        if candidate.is_file() and candidate.name == expected:
            return candidate
    return None


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=60) as resp:
        with open(dest, "wb") as out:
            shutil.copyfileobj(resp, out)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_chrome_for_testing() -> Path:
    """Download a genuine Chrome for Testing into the tool cache and return its binary."""
    plat = _platform_key()
    with urllib.request.urlopen(CHROME_FOR_TESTING_METADATA, timeout=60) as resp:
        meta = json.load(resp)

    channel = meta.get("channels", {}).get("Stable", {})
    downloads = channel.get("downloads", {}).get("chrome", [])

    entry = next((d for d in downloads if d.get("platform") == plat), None)
    if entry is None:
        raise RuntimeError(
            f"No Chrome for Testing build available for platform '{plat}'."
        )

    version = channel.get("version", "unknown")
    archive = config.browser_cache_dir() / f"chrome-{plat}-{version}.zip"
    if not archive.exists():
        print(f"No browser found — downloading Chrome for Testing {version} "
              f"({plat}) into the tool cache…")
        _download(entry["url"], archive)

    if entry.get("sha256") and _sha256(archive) != entry["sha256"]:
        raise RuntimeError("Downloaded Chrome failed its SHA-256 integrity check.")

    extract_dir = archive.with_suffix("")
    if not extract_dir.exists():
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(extract_dir)
    if sys.platform != "win32":
        binary = _binary_path_in_extracted(plat, extract_dir)
        binary.chmod(0o755)
        return binary
    return _binary_path_in_extracted(plat, extract_dir)


def resolve_browser(interactive: bool = True) -> str:
    """Return a usable browser binary, provisioning one if necessary."""
    # 1. System browser.
    try:
        return detect_browser_binary()
    except BrowserNotFoundError:
        pass

    # 2. Already downloaded into the tool cache.
    cached = cached_browser_binary()
    if cached is not None:
        return str(cached)

    # 3. Download Chrome for Testing, unless the user declines.
    if interactive:
        try:
            answer = input(
                "No Chrome/Chromium/Edge was found on this machine.\n"
                "The tool can download a genuine Chrome for Testing into its own "
                "folder (~150MB). Continue? [Y/n] "
            ).strip().lower()
        except EOFError:
            answer = ""
        if answer in ("", "y", "yes"):
            return str(download_chrome_for_testing())

    # 4. Ask the user for a path.
    if interactive:
        try:
            custom = input("Path to your Chrome/Chromium/Edge binary: ").strip()
        except EOFError:
            custom = ""
        if custom:
            resolved = Path(custom).expanduser()
            if resolved.is_file():
                return str(resolved)

    raise BrowserNotFoundError(
        "No Chrome/Chromium/Edge browser is available and the tool could not "
        "provision one. Install a browser, or pass its path to `xlogin`."
    )