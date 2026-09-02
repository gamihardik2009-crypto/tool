"""Portable manager configuration and runtime state paths.

The manager never relies on machine-specific absolute paths. Everything lives
under the user's platform-standard config directory so the tool can be dropped
onto any machine and still find/create its own state.

    state_dir  = ~/.config/telegram-x            (Linux)
               = ~/Library/Application Support/telegram-x   (macOS)
               = %APPDATA%/telegram-x            (Windows)
"""
from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

APP_NAME = "telegram-x"


def user_config_dir() -> Path:
    """Return the platform-standard per-user configuration directory."""
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_NAME
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / APP_NAME


def state_dir() -> Path:
    """Directory holding manager settings (no secrets)."""
    return user_config_dir()


def browser_profile_dir() -> Path:
    """Dedicated persistent Chromium profile used by `xlogin`.

    Keeping a persistent profile means the user only has to log into X once;
    later `xlogin` runs reuse it and just capture refreshed cookies.
    """
    return state_dir() / "browser-profile"


def session_file_path() -> Path:
    """Where the validated X session is saved locally."""
    return state_dir() / "x-session.json"


def manager_root() -> Path:
    """The manager package's own directory (portable: always relative to this file)."""
    return Path(__file__).resolve().parent.parent


def resources_root() -> Path:
    """Top-level project directory (contains the VPS worker to be deployed)."""
    return manager_root().parent


def browser_cache_dir() -> Path:
    """Where the manager keeps a downloaded browser when the OS has none.

    The manager only downloads when no system Chromium-family browser is found,
    so on most machines this stays empty. Downloads live under the tool's own
    config dir, keeping the tool self-contained and portable.
    """
    return state_dir() / "browsers"


def ssh_key_path() -> Path:
    """Ed25519 private key the manager uses to reach the VPS.

    Generated on first `connect`; kept only in the user config dir (0600).
    """
    return state_dir() / "id_ed25519"


def ssh_pub_key_path() -> Path:
    return state_dir() / "id_ed25519.pub"


def ssh_settings_path() -> Path:
    """Non-secret connection profile (host/user/port). The private key is separate."""
    return state_dir() / "connection.json"


def activity_path() -> Path:
    """Local log of the manager's most recent actions (activity history)."""
    return state_dir() / "activity.json"


def creds_path() -> Path:
    """Local credentials file (Telegram bot token + optional chat id)."""
    return state_dir() / "credentials.json"

def sync_settings_path() -> Path:
    return state_dir() / "tailscale-sync.json"
