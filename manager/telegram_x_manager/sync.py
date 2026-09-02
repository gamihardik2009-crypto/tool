from __future__ import annotations
import json, urllib.request, urllib.error
from . import config, tailscale

def save_settings(address: str, token: str) -> None:
    p = config.sync_settings_path(); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps({"address": address.strip(), "token": token.strip()}), encoding="utf-8"); p.chmod(0o600)
def load_settings() -> dict:
    try: return json.loads(config.sync_settings_path().read_text())
    except (OSError, ValueError): return {}
def sync_session() -> str:
    info = tailscale.local_info()
    if not info.installed: raise RuntimeError("Tailscale is not installed.")
    if not info.connected: raise RuntimeError("Tailscale is installed but this device is not connected.")
    s = load_settings(); address = str(s.get("address", "")).strip(); token = str(s.get("token", "")).strip()
    if not address: raise RuntimeError("VPS Tailscale address is not configured.")
    if not token: raise RuntimeError("Sync authentication token is not configured.")
    if not config.session_file_path().is_file(): raise RuntimeError("X session not found. Run `xlogin` first.")
    base = address if "://" in address else "http://" + address
    if base.endswith("/"): base = base[:-1]
    try:
        req = urllib.request.Request(base + "/health", method="GET"); urllib.request.urlopen(req, timeout=10).read()
    except Exception as exc: raise RuntimeError("VPS is not reachable through Tailscale or credential service is not running.") from exc
    payload = config.session_file_path().read_bytes()
    req = urllib.request.Request(base + "/v1/session", data=payload, method="POST", headers={"Authorization":"Bearer "+token, "Content-Type":"application/json"})
    try: urllib.request.urlopen(req, timeout=20).read()
    except urllib.error.HTTPError as exc:
        if exc.code == 401: raise RuntimeError("Authentication failed.")
        raise RuntimeError("Credential synchronization failed.")
    return "Credentials synchronized successfully."
