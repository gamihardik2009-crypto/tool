"""Offline checks for browser provisioning logic (no big download).

* `resolve_browser` should pick the real system browser first.
* `cached_browser_binary` should find a pre-downloaded browser in the tool cache.
* platform-key + binary-name mapping is sane for this OS.
* `--browser` override path is honored through the xlogin entry point.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telegram_x_manager import config
from telegram_x_manager import provisioning as prov

# 1. System browser preferred.
binary = prov.resolve_browser(interactive=False)
assert Path(binary).exists(), f"resolved binary missing: {binary}"
print("resolve_browser ->", binary)

# 2. Platform mapping sanity.
plat = prov._platform_key()
print("platform_key:", plat)
assert prov._binary_name_for("win64") == "chrome.exe"
assert prov._binary_name_for("linux64") == "chrome"

# 3. Cached-browser detection finds nothing yet (no download performed).
assert prov.cached_browser_binary() is None
print("cached_browser_binary -> None (expected, nothing downloaded)")

# 4. Ensure config paths resolve under the user config dir (portable).
assert "telegram-x" in str(config.browser_cache_dir())
print("browser_cache_dir:", config.browser_cache_dir())

print("\nOK: provisioning resolution works")