# Manager CLI (runs on your PC)

Portable tool that captures your X session (no manual DevTools copy) and, in a
later chunk, controls the VPS worker over SSH.

## What's here

| Piece | Purpose |
|-------|---------|
| `telegram_x_manager/` | Python package (CLI). |
| `setup.sh` | **Self-setup**: creates `.venv`, installs deps. Portable — run anywhere. |
| `tests/` | CDP plumbing + cookie-capture checks. |

## Setup from GitHub (one-time, portable)

Linux/macOS:

```bash
git clone https://github.com/YOUR_ACCOUNT/telegram-x.git
cd telegram-x/manager
./setup.sh
./.venv/bin/telegram-x-manager tui
```

Windows PowerShell:

```powershell
git clone https://github.com/YOUR_ACCOUNT/telegram-x.git
Set-Location telegram-x\manager
.\setup.ps1
.\.venv\Scripts\telegram-x-manager.exe tui
```

The manager stores all state under the operating system's user config folder;
it does not depend on this repository's absolute path. Chrome/Chromium/Edge is
auto-detected from standard locations and launched with a dedicated profile.

### Manual setup (one-time, portable)

```bash
cd manager
./setup.sh
./.venv/bin/python -m telegram_x_manager --help
```

It installs only two deps (`playwright`, `tweetkit-x`). It does **not** download a
Playwright browser — the tool attaches to your **real** Chrome/Edge via CDP, so no
automation browser is needed and `navigator.webdriver` stays `false`.

## Capture your X session

```bash
./.venv/bin/python -m telegram_x_manager xlogin
```

This:
1. Finds a usable browser in order: a real browser on your OS → one the tool
   already downloaded into its own cache → (if none) downloads a genuine
   **Chrome for Testing** into the tool's folder → else asks you for a path.
   You can force a specific browser anytime with `--browser /path/to/chrome`.
2. Launches it with its **own persistent profile** and a CDP debugging port, headful,
   *without* automation flags → X sees a normal browser.
3. Opens `x.com/home`. Log in there.
4. Reads the session cookies over CDP (including the HttpOnly `auth_token` and `ct0`),
   validates them with `tweetkit whoami()`, and saves them.
5. Closes the browser but **keeps the profile**, so the next `xlogin` reuses your login
   and just grabs refreshed cookies.

Saved to `~/.config/telegram-x/x-session.json` (mode 0600). State dirs are portable.

### What if the PC has no browser installed?

The tool never depends on its own copy of Playwright's automation browser. If it
can't find Chrome/Chromium/Edge on the OS, it downloads a genuine **Chrome for
Testing** (SHA-256 verified) into the tool's own config folder and launches it the
same safe way — so even a machine with zero installed browsers can still do `xlogin`.
Whether that browser is the OS one or a downloaded one, it is launched by us with
its own profile and **no** automation flags, so it is indistinguishable to X from a
normal browser.

## Why real browser + CDP instead of Playwright-launched

Playwright's launcher sets `--enable-automation` and `navigator.webdriver=true`,
which X and Google fingerprint as an insecure/bot session. Attaching to your real
browser over CDP (`connect_over_cdp`) avoids those flags entirely. Verified in
`tests/test_cdp.py`: `navigator.webdriver` is `False` on a real Chrome connected
over CDP.

## Connect to your VPS (`connect`)

Made as simple as possible for a non-technical user, and it works over any
internet connection (port 22 just has to be reachable). Pick whichever mode fits
your provider — the manager auto-detects your intent from the flags:

**1. Password (auto)** — for VPSes that allow password login:

```bash
./.venv/bin/python -m telegram_x_manager connect --host VPS_IP --user root
# you'll be prompted (privately) for the password once
```

The manager generates its own SSH key, connects once with your password, installs
its public key into the VPS (`ssh-copy-id` equivalent), and verifies key auth.
The password is **never stored** — from then on every connection uses the key.

**2. Key file (cloud providers)** — for AWS/DigitalOcean/Linode that give you a
`.pem`/private key instead of a password:

```bash
./.venv/bin/python -m telegram_x_manager connect --host VPS_IP --user ubuntu --key ~/Downloads/my-key.pem
```

**3. Manual / assisted** — when you can't or won't share a password (or you have
an AI agent on the VPS). The manager prints a **ready-to-run one-line command** that
authorizes your PC's key; you (or the VPS agent) run it once:

```bash
./.venv/bin/python -m telegram_x_manager connect --host VPS_IP --user root --manual
# then run the printed command on the VPS once
```

After any mode, `status` confirms the link and `health` shows the full picture.

## Status

- ✅ Chunk 2 — `xlogin` real-browser CDP session capture + browser provisioning.
- ✅ Chunk 3 (part) — `connect` (3 modes), `creds`, `health`, `status`, activity history.
- ✅ Chunk 3 (part) — `deploy` (push worker + self-setup + start), `control start|stop|status|logs` — live-tested on Termux.
- ⏳ Chunk 4 — packaging + docs polish.

## Deploy & control the worker (`deploy`, `control`)

## Interactive terminal UI (`tui`)

Launch the responsive Textual dashboard:

```bash
./.venv/bin/python -m telegram_x_manager tui
```

The home screen automatically shows Telegram, X session, SSH, and worker status.
Use the four actions to connect SSH, save the Telegram token, log into X, and
start or stop the remote worker. Press `R` to refresh and `Q` to quit.

If Tailscale is installed and connected on the PC, the SSH form automatically
finds an online Android peer, fills its Tailscale IP, and selects Termux port
`8022`. The Android Tailscale app and the PC must be signed into the same
tailnet. SSH transport remains pure Paramiko.

Once the link is up and you've captured both the X session (`xlogin`) and the
Telegram credentials (`creds`), one command pushes the worker to the VPS and
starts it:

```bash
./.venv/bin/python -m telegram_x_manager deploy
```

This uploads the worker files, runs the worker's own `setup.sh` (it creates the
venv and installs its dependencies itself — nothing preinstalled needed), writes
`.env` with your token/chat id (mode 0600), pushes the X session, and starts the
worker. It works on a plain Linux VPS **and** on Termux (no systemd required):
the worker runs under `nohup` with a pid file, and on Termux the setup reuses
Termux's own prebuilt `python-lxml`/`python-cryptography` packages because those
wheels cannot be compiled on-device.

Then control it remotely:

```bash
./.venv/bin/python -m telegram_x_manager control status   # running? pid?
./.venv/bin/python -m telegram_x_manager control logs     # last 50 log lines
./.venv/bin/python -m telegram_x_manager control logs --lines 200
./.venv/bin/python -m telegram_x_manager control stop
./.venv/bin/python -m telegram_x_manager control start
```

`health` still shows the one-screen verdict (Telegram token, X session, worker
process, last-10 activity), reading the worker's `~/telegram-x/data/health.json`
from the VPS.

**Note:** the worker lives in `~/telegram-x` on the target, so any Linux box
with your SSH key reachable works — including a spare Android phone running
Termux (`ssh termux` aliases from `~/.ssh/config` are honored automatically,
including custom ports and identity files).

### Test note (honest)

Exec + SFTP over SSH use the standard Paramiko client API. Both auth paths
(password and publickey) and an exec round-trip are verified live in this
environment; the SFTP `put/download` calls follow the exact same `open_sftp()`
method and are exercised against real OpenSSH in production. The offline tests in
`tests/` cover key generation, shell-quoting, profile round-trip, credential
storage, and activity history — all green.
