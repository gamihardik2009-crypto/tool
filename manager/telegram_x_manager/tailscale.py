from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass


def online_peers() -> list[dict[str, str]]:
    """Return online Tailscale peers without requiring Tailscale as a dependency."""
    binary = shutil.which("tailscale")
    if not binary:
        return []
    try:
        result = subprocess.run(
            [binary, "status", "--json"], capture_output=True, text=True,
            timeout=8, check=True,
        )
        payload = json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return []

    peers = []
    for peer in (payload.get("Peer") or {}).values():
        if not peer.get("Online"):
            continue
        addresses = peer.get("TailscaleIPs") or []
        if not addresses:
            continue
        peers.append({
            "name": peer.get("HostName") or peer.get("DNSName", "").rstrip("."),
            "ip": addresses[0],
            "os": str(peer.get("OS") or "").lower(),
        })
    return peers


def preferred_termux_peer() -> dict[str, str] | None:
    peers = online_peers()
    return next((peer for peer in peers if peer["os"] == "android"), peers[0] if peers else None)

@dataclass
class TailscaleInfo:
    installed: bool
    connected: bool
    ip: str = ""
    hostname: str = ""
    detail: str = ""

def setup(auth_key: str | None = None) -> str:
    """Install/start Tailscale where possible, then authenticate with an auth key."""
    binary = shutil.which("tailscale")
    if not binary:
        if shutil.which("pkg"):
            try:
                subprocess.run(["pkg", "install", "-y", "tailscale"], check=True, timeout=180)
                binary = shutil.which("tailscale") or "tailscale"
            except (OSError, subprocess.CalledProcessError) as exc:
                raise RuntimeError("Tailscale is unavailable in this Termux repository; install the Tailscale Android app, then rerun setup.") from exc
        elif not shutil.which("curl"):
            raise RuntimeError("Tailscale is not installed and curl is unavailable.")
        else:
            subprocess.run(["sh", "-c", "curl -fsSL https://tailscale.com/install.sh | sh"], check=True, timeout=180)
            binary = shutil.which("tailscale") or "tailscale"
    if shutil.which("systemctl"):
        subprocess.run(["systemctl", "enable", "--now", "tailscaled"], check=False, timeout=30)
    cmd = [binary, "up"]
    if auth_key: cmd += ["--auth-key", auth_key]
    try: subprocess.run(cmd, check=True, timeout=120)
    except subprocess.CalledProcessError as exc: raise RuntimeError("Tailscale needs authorization. Run `tailscale up` and follow the login URL, or provide --auth-key.") from exc
    info = local_info()
    return f"Tailscale connected: {info.ip or info.hostname}"

def local_info() -> TailscaleInfo:
    binary = shutil.which("tailscale")
    if not binary:
        return TailscaleInfo(False, False, detail="Tailscale is not installed.")
    try:
        data = json.loads(subprocess.run([binary, "status", "--json"], capture_output=True, text=True, timeout=8, check=True).stdout)
        self_data = data.get("Self") or {}
        ips = self_data.get("TailscaleIPs") or []
        online = bool(self_data.get("Online", False))
        return TailscaleInfo(True, online, next((x for x in ips if ":" not in x), ips[0] if ips else ""),
                             self_data.get("HostName") or self_data.get("DNSName", "").rstrip("."),
                             "connected" if online else "Tailscale is installed but this device is not connected.")
    except Exception as exc:
        return TailscaleInfo(True, False, detail=f"Unable to query Tailscale: {exc}")
