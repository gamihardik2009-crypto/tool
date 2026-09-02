"""telegram_x_manager — CLI to control a Telegram→X VPS worker from your PC.

Commands:
  * xlogin   – capture/refresh the X session via your real browser (CDP).
  * connect  – one-time, password-based setup of key-based SSH access to the VPS
               (thereafter every op is key-auth, no password).
  * creds    – store the Telegram bot token + chat id locally.
  * health   – show telegram pipeline, X session, workflow connection, activity.
  * status   – quickly test the SSH connection to the VPS.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from . import config


def add_xlogin_parser(sub) -> None:
    p = sub.add_parser("xlogin", help="Log into X in a real browser and save the session")
    p.add_argument("--port", type=int, default=None,
                   help="CDP debugging port (default: auto-pick a free one)")
    p.add_argument("--max-wait", type=float, default=300.0,
                   help="Seconds to wait for the X login (default: 300)")
    p.add_argument("--session", type=str, default=None,
                   help="Output session file path (default: the manager state dir)")
    p.add_argument("--browser", type=str, default=None,
                   help="Explicit path to a Chrome/Chromium/Edge binary (skips auto-detection)")
    p.set_defaults(func=cmd_xlogin)


def cmd_xlogin(args) -> int:
    from . import activity
    from .session import xlogin
    try:
        session_path = config.session_file_path() if not args.session else Path(args.session).expanduser()
        profile_dir = config.browser_profile_dir()
        xlogin(session_path, profile_dir, port=args.port, max_wait=args.max_wait,
               browser_path=args.browser)
        activity.record("xlogin", True, f"session saved → {session_path}")
        return 0
    except Exception as exc:
        activity.record("xlogin", False, str(exc))
        print(f"❌ xlogin failed: {exc}")
        return 1


def add_connect_parser(sub) -> None:
    p = sub.add_parser("connect", help="Set up access to the VPS")
    p.add_argument("--host", help="VPS IP or hostname")
    p.add_argument("--user", help="VPS SSH username")
    p.add_argument("--port", type=int, default=22)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--password", help="VPS SSH password (auto-installs the manager key)")
    g.add_argument("--key", help="Path to an existing private key / .pem (cloud VPS)")
    p.add_argument("--manual", action="store_true",
                   help="Print ready-to-run instructions to authorize the manager key manually")
    p.set_defaults(func=cmd_connect)


def cmd_connect(args) -> int:
    from pathlib import Path as _Path
    from . import activity
    from .remote import (
        ConnectionProfile, bootstrap, save_profile,
        verify_connection, manual_instructions,
    )

    try:
        host = args.host or input("VPS IP/hostname: ").strip()
        user = args.user or input("VPS SSH username [root]: ").strip() or "root"
        if not host:
            raise SystemExit("Host is required.")
        port = args.port or 22
        profile = ConnectionProfile(host=host, username=user, port=port)

        if args.manual:
            # Mode 3: no password/key shared — user (or VPS AI agent) runs a command once.
            save_profile(profile)
            print(manual_instructions())
            print("Key-based SSH is set up on this PC. Run the command above on the")
            print("VPS once, then run `status` to confirm the connection works.")
            activity.record("connect", True, f"manual setup prepared for {user}@{host}")
            return 0

        if args.key:
            # Mode 2: existing key file (cloud providers, e.g. .pem).
            key_path = _Path(args.key).expanduser()
            if not key_path.is_file():
                raise SystemExit(f"Key file not found: {key_path}")
            save_profile(profile)
            username = verify_connection(profile, key_filename=str(key_path))
            activity.record("connect", True, f"linked via key file to {user}@{host}")
            print(f"✅ Connected to {username}@{host} using your key file.")
            print("Next: run `creds` to add your Telegram token, then `deploy`.")
            return 0

        # Reuse an existing SSH config alias/key when available (for example
        # `ssh termux`), avoiding an unnecessary password bootstrap.
        if not args.password:
            try:
                username = verify_connection(profile)
            except Exception:
                pass
            else:
                save_profile(profile)
                activity.record("connect", True, f"linked via existing SSH config to {user}@{host}")
                print(f"✅ Connected to {username}@{host} using your SSH config key.")
                print("Next: run `creds` to add your Telegram token, then `deploy`.")
                return 0

        # Mode 1: password auto-bootstrap.
        bootstrap(host=host, port=port, username=user,
                  password=args.password or None)
        activity.record("connect", True, f"linked to {user}@{host} (key installed)")
        print(f"\n✅ Connected and linked to {user}@{host}.")
        print("Key-based SSH is now set up — you won't need the password again.")
        print("Next: run `creds` to add your Telegram token, then `deploy`.")
        return 0
    except Exception as exc:
        activity.record("connect", False, str(exc))
        print(f"❌ connect failed: {exc}")
        print("Check that the host is reachable and port 22 is open. If your VPS")
        print("doesn't accept passwords, use `--key /path/to/key.pem` or `--manual`.")
        return 1


def add_creds_parser(sub) -> None:
    p = sub.add_parser("creds", help="Store the Telegram bot token + chat id locally")
    p.add_argument("--token", help="Telegram bot token from @BotFather")
    p.add_argument("--chat-id", help="Optional Telegram group id (negative number)")
    p.set_defaults(func=cmd_creds)

def add_tailscale_parser(sub) -> None:
    p = sub.add_parser("tailscale", help="Configure and test the Tailscale credential link")
    p.add_argument("action", choices=["status", "configure", "test", "sync"])
    p.add_argument("--address", help="VPS Tailscale IP, MagicDNS hostname, or URL")
    p.add_argument("--token", help="Application sync token (stored locally with mode 0600)")
    p.set_defaults(func=cmd_tailscale)

def cmd_tailscale(args) -> int:
    from . import tailscale, sync
    try:
        if args.action == "status":
            i = tailscale.local_info(); print(f"installed: {'yes' if i.installed else 'no'}\nconnected: {'yes' if i.connected else 'no'}\nip: {i.ip or '-'}\nhostname: {i.hostname or '-'}\n{i.detail}"); return 0 if i.installed and i.connected else 1
        if args.action == "configure":
            if not args.address or not args.token: raise RuntimeError("--address and --token are required")
            sync.save_settings(args.address, args.token); print("Tailscale VPS address and sync token saved."); return 0
        if args.action == "test":
            s = sync.load_settings(); import urllib.request
            address = str(s.get("address", "")).strip()
            if not address: raise RuntimeError("VPS Tailscale address is not configured.")
            base = address if "://" in address else "http://" + address
            urllib.request.urlopen(base.rstrip("/") + "/health", timeout=10).read(); print("VPS credential service is reachable through Tailscale."); return 0
        print(sync.sync_session()); return 0
    except Exception as exc:
        print(f"Tailscale operation failed: {exc}"); return 1


def cmd_creds(args) -> int:
    import getpass
    from . import activity, creds
    from .health import check_bot_token
    try:
        token = args.token or getpass.getpass("Telegram bot token (hidden): ").strip()
        if not token:
            raise SystemExit("Bot token is required.")
        chat_id = args.chat_id if args.chat_id is not None else input("Telegram chat id (optional): ").strip()
        creds.save(token, chat_id)
        print("Credentials stored locally.")
        result = check_bot_token(token)
        mark = "valid" if result.get("ok") else "rejected"
        activity.record("creds", bool(result.get("ok")),
                        f"bot token {mark} {result.get('detail', '')}")
        print(f"Bot token check: {mark} — {result.get('detail', '')}")
        return 0
    except Exception as exc:
        activity.record("creds", False, str(exc))
        print(f"❌ creds failed: {exc}")
        return 1


def add_health_parser(sub) -> None:
    p = sub.add_parser("health", help="Show manager, telegram, X, workflow and activity status")
    p.set_defaults(func=cmd_health)


def cmd_health(_args) -> int:
    from . import activity
    from .health import run_checks, render
    try:
        report = run_checks()
        print(render(report))
        activity.record("health", True, "health report shown")
        return 0
    except Exception as exc:
        activity.record("health", False, str(exc))
        print(f"❌ health failed: {exc}")
        return 1


def add_status_parser(sub) -> None:
    p = sub.add_parser("status", help="Quickly test the SSH connection to the VPS")
    p.set_defaults(func=cmd_status)


def cmd_status(_args) -> int:
    from . import activity
    from .remote import Remote, RemoteError, load_profile
    profile = load_profile()
    if profile is None:
        print("Not connected — run `connect` first.")
        return 1
    try:
        with Remote() as remote:
            remote.run("echo ok; id -un")
        print(f"✅ Connected to {profile.username}@{profile.host}:{profile.port}")
        activity.record("status", True, f"connected to {profile.host}")
        return 0
    except RemoteError as exc:
        activity.record("status", False, str(exc))
        print(f"❌ Not connected: {exc}")
        return 1


def add_deploy_parser(sub) -> None:
    p = sub.add_parser("deploy", help="Push the worker to the VPS and start it")
    p.add_argument("--token", help="Telegram bot token (default: the stored one)")
    p.add_argument("--chat-id", help="Optional Telegram group id")
    p.add_argument("--session", help="Path to X session file (default: the captured one)")
    p.set_defaults(func=cmd_deploy)


def cmd_deploy(args) -> int:
    from . import activity
    from .worker import WorkerController
    try:
        ctl = WorkerController()
        out = ctl.deploy(token=args.token, chat_id=args.chat_id,
                         session_path=Path(args.session) if args.session else None)
        print(out)
        activity.record("deploy", True, "worker deployed and started")
        return 0
    except Exception as exc:
        activity.record("deploy", False, str(exc))
        print(f"❌ deploy failed: {exc}")
        return 1


def add_control_parser(sub) -> None:
    p = sub.add_parser("control", help="start, stop, status or logs the worker on the VPS")
    p.add_argument("action", choices=["start", "stop", "status", "logs"])
    p.add_argument("--lines", type=int, default=50, help="lines for `logs`")
    p.set_defaults(func=cmd_control)


def add_history_parser(sub) -> None:
    p = sub.add_parser("history", help="Show recent manager activity")
    p.add_argument("--lines", type=int, default=15)
    p.set_defaults(func=cmd_history)


def cmd_history(args) -> int:
    from .activity import history
    for entry in history(max(1, args.lines)):
        mark = "OK" if entry.get("ok") else "FAIL"
        print(f"{mark} {entry.get('ts', '')} {entry.get('action', '')} - {entry.get('detail', '')}")
    return 0


def cmd_tui(_args) -> int:
    from .tui import run
    return run()


def cmd_control(args) -> int:
    from . import activity
    from .worker import WorkerController
    try:
        out = WorkerController().run_action(args.action, args.lines)
        print(out)
        if args.action in ("start", "stop"):
            activity.record("control/" + args.action, True, "worker " + args.action)
        return 0
    except Exception as exc:
        activity.record("control/" + args.action, False, str(exc))
        print(f"❌ {args.action} failed: {exc}")
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="telegram-x-manager",
        description="Control a Telegram→X VPS worker from your PC.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    add_xlogin_parser(sub)
    add_connect_parser(sub)
    add_creds_parser(sub)
    add_tailscale_parser(sub)
    add_health_parser(sub)
    add_status_parser(sub)
    add_deploy_parser(sub)
    add_control_parser(sub)
    add_history_parser(sub)
    sub.add_parser("tui", help="Open the interactive terminal interface").set_defaults(func=cmd_tui)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))
