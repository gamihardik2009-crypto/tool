# Telegram → X Automation (new project)

A small Python system that listens to a Telegram group with your bot and posts each
text message or **photo** to X (Twitter). It runs headlessly on a **VPS** and is
controlled from your own **PC** by a CLI **manager** tool.

Built on `python-telegram-bot` and `tweetkit-x` (X's internal endpoints are replayed
using your own logged-in web session — no paid X API, no developer app).

> This is the fresh project. The core worker was carried over from the earlier
> prototype (which was ~80% done and tested for Telegram→X posting) because that
> part is proven. The **manager** tool is being built new here and is the focus.

---

## Two components

### 1. VPS Worker (the proven core, runs headless)

| File              | What it does                                                        |
|-------------------|--------------------------------------------------------------------|
| `main.py`         | Entry point: long-polls Telegram, wires everything together.       |
| `collector.py`    | Turns each Telegram `Message` into a record; posts text/photo.     |
| `x_publisher.py`  | Adapter around `tweetkit-x`; posts with a 280-char limit, auto-reloads the session. |
| `session_keeper.py`| Headless Playwright/Chromium on the VPS that refreshes the X cookie session. |
| `database.py`     | SQLite storage, dedupes by `(chat_id, message_id)`.                |
| `health.py`       | Atomic, non-secret health state for remote inspection.             |
| `config.py`       | Loads settings from a `.env` file (no extra dependency).           |
| `deploy/`         | systemd units + `install.sh` for the VPS.                          |

### 2. Manager CLI (`manager/`) — runs on your PC — being built (Chunks 2–4)

Planned commands (see the roadmap below):

- **`xlogin`** — opens a *visible* browser on your PC, you log into X, it grabs the
  session cookie automatically (including the HttpOnly `auth_token`), validates it,
  and saves it locally. **This removes the manual DevTools/HAR step and solves the
  "can't log into X on the VPS" problem.**
- **`connect`** — SSH to the VPS, test the connection, remember host/user/key.
- **`deploy`** — copy the worker to the VPS and install/start the services.
- **`creds`** — store the Telegram bot token + chat ID locally and push them (with the
  X session) to the VPS, then restart the worker.
- **`start` / `stop` / `status` / `logs` / `health` / `session-status`** — control the VPS.

---

## Setup (current — Chunk 1)

For now, only the worker is scaffolded. To run it on a machine that already has an
X session file and a Telegram bot token:

```bash
sh setup.sh                # creates .venv, installs deps, writes default .env
./.venv/bin/python main.py # or: sh run.sh start   (background + pid file + logs)
```

`setup.sh` is portable — it works on a plain Linux VPS **and** on Termux (where it
reuses Termux's prebuilt `python-lxml` / `python-cryptography`, since those wheels
can't be compiled on-device). `run.sh start|stop|status|logs` manages the worker
without needing systemd.

Your bot must be **admin** of the group and **Group Privacy Mode disabled** in
@BotFather so it receives every message. `X_SESSION_PATH` points to a flat X cookie
session (the format `tweetkit-x` expects). `requirements.txt` is the portable core;
`requirements-full.txt` additionally includes Playwright for the VPS session keeper.

---

## Chunk roadmap

- [x] **Chunk 1** — project folder, worker carried over + verified, README.
- [x] **Chunk 2** — manager `xlogin`: attach to your *real* browser over CDP (no Playwright-launched automation browser), auto-capture + validate the X session. Browser self-provisioning if the OS has none.
- [x] **Chunk 3 (part)** — manager `connect` (3 modes: password-auto, key-file, manual), `creds`, `health`, `status`, activity history.
- [x] **Chunk 3 (part)** — manager `deploy` (push worker + self-setup + start) and `control start|stop|status|logs` over SSH; portable `setup.sh`/`run.sh` (works on VPS and Termux, no systemd needed); live-tested on Termux.
- [ ] **Chunk 4** — packaging, docs, small tests, polish.

## Security notes

- Secrets (Telegram token, X cookies) are never committed to git.
- The manager stores credentials in your OS keyring, not plaintext (planned).
- Live on the VPS, secrets live in `/etc/telegram-x/` (root-only), owned by the
  locked-down `telegram-x` service account.

## Tailscale credential sync (CGNAT-safe)

Both the PC and VPS may use mobile Internet, dynamic addresses, and carrier CGNAT. No public/static IP, inbound client connection, router configuration, or port forwarding is required: Tailscale provides the encrypted private path and may use its normal DERP relay when direct peer-to-peer is unavailable.

### VPS

Install and authenticate Tailscale using the official package for your OS, then verify it:

```bash
sudo tailscale up
tailscale ip -4
tailscale status
```

After deploying the project, create `/etc/telegram-x/sync.env` (mode `600`), binding only to the Tailscale interface address:

```bash
SYNC_BIND=100.x.y.z
SYNC_PORT=8787
X_SESSION_PATH=/opt/telegram-x/data/x-session.json
TELEGRAM_X_SYNC_TOKEN=<long-random-secret>
```

Install/start `deploy/telegram-x-sync.service` (or run the receiver with these variables). Do not expose port 8787 publicly; allow it only in your Tailscale ACL/firewall.

For a systemd install after copying the project to `/opt/telegram-x`:

```bash
sudo install -m 0644 deploy/telegram-x-sync.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now telegram-x-sync
sudo systemctl status telegram-x-sync
```

### Client

Install and authenticate Tailscale, then configure the VPS MagicDNS name or `100.x.y.z` address and the same application token:

```bash
python -m telegram_x_manager tailscale status
python -m telegram_x_manager tailscale configure --address http://vps-name:8787 --token '<long-random-secret>'
python -m telegram_x_manager tailscale test
python -m telegram_x_manager xlogin
python -m telegram_x_manager tailscale sync
```

The client initiates every request. Tokens and X cookies are never placed in URLs or logs. `tailscale test` checks the service before upload and reports whether Tailscale, the address, service, or application authentication is the failing layer. Existing `connect`, `deploy`, and `control` SSH commands remain available for VPS administration and worker deployment; credential synchronization does not depend on SSH.
