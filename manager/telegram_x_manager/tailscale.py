from __future__ import annotations

import json
import shutil
import subprocess


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
