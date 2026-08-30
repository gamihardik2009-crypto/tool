"""Simplified SSH layer for non-technical users, via Paramiko.

Instead of asking a non-technical user to generate SSH keys, copy them onto the
VPS and edit `authorized_keys`, the manager does it for them in one step:

  `connect`  →  user enters only host + username + password (once)
             →  manager generates an Ed25519 keypair locally
             →  connects with the password, installs its public key into the
                VPS account's `~/.ssh/authorized_keys` (what `ssh-copy-id` does)
             →  verifies key-based auth works, then forgets the password

After that every operation uses the key. Pure Python (Paramiko), so it needs no
system `ssh`/`scp` binaries and works over any TCP/IP internet connection.

The private key stays in the manager's own config dir (0600); the password is
never saved.
"""
from __future__ import annotations

import getpass
import os
from dataclasses import dataclass, asdict
from pathlib import Path

import paramiko

from . import config


@dataclass
class ConnectionProfile:
    host: str
    username: str
    port: int = 22


def load_profile(path: Path | None = None) -> ConnectionProfile | None:
    import json
    path = path or config.ssh_settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return ConnectionProfile(**data)
    except (OSError, ValueError, TypeError):
        return None


def save_profile(profile: ConnectionProfile, path: Path | None = None) -> None:
    import json
    path = path or config.ssh_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(profile), indent=2), encoding="utf-8")
    os.chmod(path, 0o600)


def ensure_keypair() -> tuple[Path, str]:
    """Generate an SSH keypair in the manager config dir.

    Uses RSA: its `.generate()` is stable across all paramiko versions (paramiko
    5.x changed the Ed25519 generation API) and RSA is universally accepted by
    OpenSSH servers. Returns (privkey_path, public_key_line). Reuses an existing
    key if present.
    """
    priv = config.ssh_key_path()
    pub = config.ssh_pub_key_path()
    if not priv.exists():
        priv.parent.mkdir(parents=True, exist_ok=True)
        key = paramiko.RSAKey.generate(bits=3072)
        key.write_private_key_file(str(priv))
        os.chmod(priv, 0o600)
        pub.write_text(
            f"{key.get_name()} {key.get_base64()} telegram-x-manager\n",
            encoding="utf-8",
        )
        os.chmod(pub, 0o644)
    public_line = pub.read_text(encoding="utf-8").strip()
    return priv, public_line


class RemoteError(RuntimeError):
    pass


def quote(value: str) -> str:
    """Single-quote a string for safe shell use."""
    return "'" + value.replace("'", "'\\''") + "'"


class Remote:
    """A thin Paramiko client bound to the saved profile + manager key."""

    def __init__(self, profile: ConnectionProfile | None = None,
                 password: str | None = None, key_filename: str | None = None) -> None:
        self.profile = profile or load_profile()
        if self.profile is None:
            raise RemoteError("No connection profile. Run the `connect` command first.")
        self.password = password
        self.key_filename = key_filename
        self.client: paramiko.SSHClient | None = None
        self._home: str | None = None

    def home(self) -> str:
        """Absolute remote home dir (SFTP does not expand `~`)."""
        if self._home is None:
            code, out = self.run("cd ~/ && pwd")
            if code != 0 or not out.strip():
                raise RemoteError("Could not resolve remote home directory.")
            self._home = out.strip().splitlines()[-1]
        return self._home

    def _abs(self, remote_path: str) -> str:
        if remote_path.startswith("~/"):
            return self.home() + "/" + remote_path[2:]
        if remote_path == "~":
            return self.home()
        return remote_path

    def _connect_kwargs(self) -> dict:
        kwargs = {"username": self.profile.username, "timeout": 15,
                  "banner_timeout": 15, "auth_timeout": 15}
        if self.password:
            kwargs["password"] = self.password
            return kwargs
        if self.key_filename:
            kwargs["key_filename"] = self.key_filename
            return kwargs
        priv, _ = ensure_keypair()
        kwargs["key_filename"] = str(priv)
        return kwargs

    def _resolve_ssh_config(self) -> None:
        """If profile.host is an alias in ~/.ssh/config, use the real values.

        Lets users reuse aliases they already have (`ssh termux`), including
        custom ports and identity files.
        """
        cfg_path = Path.home() / ".ssh" / "config"
        if not cfg_path.is_file():
            return
        try:
            cfg = paramiko.config.SSHConfig()
            with open(cfg_path, encoding="utf-8") as handle:
                cfg.parse(handle)
            if self.profile.host not in cfg.get_hostnames():
                return
            entry = cfg.lookup(self.profile.host)
            if entry.get("hostname"):
                self.profile.host = entry["hostname"]
            if entry.get("port"):
                try:
                    self.profile.port = int(entry["port"])
                except (TypeError, ValueError):
                    pass
            if entry.get("user") and (not self.profile.username or self.profile.username == getpass.getuser()):
                self.profile.username = entry["user"]
            files = entry.get("identityfile") or []
            if files and not self.key_filename:
                self.key_filename = files[0]
        except Exception:
            pass

    def open(self) -> None:
        self._resolve_ssh_config()
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(self.profile.host, port=self.profile.port,
                       **self._connect_kwargs())
        self.client = client

    def close(self) -> None:
        if self.client:
            self.client.close()
            self.client = None

    def __enter__(self) -> "Remote":
        self.open()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def run(self, command: str, timeout: float = 30) -> tuple[int, str]:
        """Run a remote command; returns (exit_status, combined_output)."""
        if self.client is None:
            raise RemoteError("Not connected.")
        stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        code = stdout.channel.recv_exit_status()
        return code, (out + err).strip()

    def put_bytes(self, data: bytes, remote_path: str) -> None:
        if self.client is None:
            raise RemoteError("Not connected.")
        sftp = self.client.open_sftp()
        try:
            with sftp.file(self._abs(remote_path), "wb") as handle:
                handle.write(data)
        finally:
            sftp.close()

    def download(self, remote_path: str, timeout: float = 15) -> str:
        if self.client is None:
            raise RemoteError("Not connected.")
        sftp = self.client.open_sftp()
        try:
            with sftp.file(self._abs(remote_path), "rb") as handle:
                return handle.read().decode("utf-8", "replace")
        finally:
            sftp.close()


def bootstrap(host: str, port: int, username: str,
              password: str | None = None) -> str:
    """One-time setup: install the manager's public key on the VPS.

    Uses the user's password (prompted if not given) to connect once and append
    our public key to the account's authorized_keys, then verifies key auth.
    Returns the installed public key line. The password is never stored.
    """
    password = password or getpass.getpass("VPS SSH password: ")

    _, public_line = ensure_keypair()
    profile = ConnectionProfile(host=host, username=username, port=port or 22)
    bootstrap_remote = Remote(profile, password=password)
    bootstrap_remote.open()

    # ssh-copy-id equivalent: ensure ~/.ssh exists and append our public key once.
    try:
        cmd = (
            "mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
            "touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && "
            f"grep -qF {quote(public_line)} ~/.ssh/authorized_keys || "
            f"echo {quote(public_line)} >> ~/.ssh/authorized_keys"
        )
        code, out = bootstrap_remote.run(cmd)
        if code != 0:
            raise RemoteError(f"Could not install SSH key: {out}")
    finally:
        bootstrap_remote.close()

    # Verify key-based auth (no password) now works.
    verify = Remote(profile)
    verify.open()
    try:
        code, out = verify.run("id -un")
        if code != 0 or not out.strip():
            raise RemoteError("Key verification failed.")
    finally:
        verify.close()

    save_profile(profile)
    return public_line


def verify_connection(profile: ConnectionProfile,
                      key_filename: str | None = None) -> str:
    """Connect using key auth (manager key or an existing key file) and verify by
    running a harmless command. Returns the username reported by the server."""
    conn = Remote(profile, key_filename=key_filename)
    conn.open()
    try:
        code, out = conn.run("id -un")
        if code != 0 or not out.strip():
            raise RemoteError("Connected but could not confirm the user.")
        return out.strip().splitlines()[0]
    finally:
        conn.close()


def manual_instructions() -> str:
    """Return the one-line command the user (or a VPS-side AI agent) can run to
    authorize the manager's key on the VPS without sharing a password."""
    _, public_line = ensure_keypair()
    return (
        "To finish connecting, run this ONE command on the VPS "
        "(as the same user you'll use to log in):\n\n"
        f"    mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo {quote(public_line)} >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys\n\n"
        "You can run it in your VPS provider's web console/terminal, or paste it "
        "into `~/.ssh/authorized_keys` (add the line below to that file):\n\n"
        f"    {public_line}\n"
    )
