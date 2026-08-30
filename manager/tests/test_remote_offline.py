"""Offline checks for remote/SSH helpers, credentials, profile and activity.

These validate the non-network parts of the SSH layer (key generation, profile
round-trip, shell-quoting) plus credential storage and the activity-history log.
A live SSH server connection is not exercised here.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telegram_x_manager import activity, creds
from telegram_x_manager.remote import (
    ConnectionProfile, ensure_keypair, load_profile, save_profile, quote,
)

tmp = Path(tempfile.mkdtemp(prefix="tzx-remote-"))

# 1. SSH key generation is idempotent and produces a valid public line.
key, pub = ensure_keypair()
assert key.exists(), "private key not created"
assert pub.startswith("ssh-"), f"bad public key: {pub!r}"
mode = key.stat().st_mode & 0o777
assert mode == 0o600, f"private key mode {oct(mode)} (expected 600)"
key2, pub2 = ensure_keypair()  # re-run reuses the same key
assert pub == pub2, "keypair was regenerated instead of reused"
print("OK ensure_keypair (created, chmod 600, idempotent)")

# 2. Shell quoting prevents injection.
assert quote("bitwalker's data; rm -rf ~") == "'bitwalker'\\''s data; rm -rf ~'"
print("OK quote is injection-safe")

# 3. Profile round-trip.
prof = ConnectionProfile(host="203.0.113.7", username="deploy", port=2222)
p = tmp / "connection.json"
save_profile(prof, p)
assert load_profile(p) == prof
print("OK profile save/load round-trip")

# 4. Credential storage round-trip (token redacted in output, never printed).
c = tmp / "creds.json"
creds.save("123456:ABC-SECRET-TOKEN", "-100123456", c)
assert creds.bot_token(c) == "123456:ABC-SECRET-TOKEN"
assert creds.chat_id(c) == "-100123456"
assert (c.stat().st_mode & 0o777) == 0o600
print("OK creds save/load (chmod 600)")

# 5. Activity history is trimmed to the newest N (default 10).
hist = tmp / "activity.json"
for i in range(15):
    activity.record(f"action-{i}", ok=True, detail="d", path=hist)
entries = activity.history(limit=10, path=hist)
assert len(entries) == 10, f"expected 10, got {len(entries)}"
assert entries[0]["action"] == "action-5", entries[0]["action"]
assert entries[-1]["action"] == "action-14"
print("OK activity history trimmed to newest 10")

print("\nAll remote/credential/activity checks passed.")