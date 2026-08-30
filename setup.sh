#!/bin/sh
# Portable self-setup for the Telegram→X worker. Run once, anywhere (Linux VPS,
# Termux, any machine) — no root required. Creates its own .venv, installs its
# dependencies, writes a default .env, and makes the data dir.
#   Use:  sh setup.sh
set -eu
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
echo "Creating local virtualenv (.venv) ..."
# Termux: reuse its prebuilt heavy packages (lxml, cryptography) — wheels for
# Android/aarch64 often cannot be compiled on-device.
if [ ! -d .venv ]; then
  if [ -n "${TERMUX_VERSION:-}" ] || [ -n "${PREFIX:-}" ] && [ "${PREFIX:-#}" != "${PREFIX#*com.termux}" ]; then
    "$PY" -m venv --system-site-packages .venv
  else
    "$PY" -m venv .venv
  fi
fi
# Termux venvs sometimes lack pip; make sure it exists.
"$PY" -m ensurepip --upgrade >/dev/null 2>&1 || true

echo "Installing worker dependencies ..."
./.venv/bin/pip install --upgrade pip >/dev/null 2>&1 || true
./.venv/bin/pip install -r requirements.txt

# Default .env so the worker can run straight away. The manager overwrites this
# with the real Telegram token + chat id when it deploys.
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
  else
    cat > .env <<'EOF'
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
DATABASE_PATH=data/messages.db
LOG_PATH=data/collector.log
X_SESSION_PATH=data/x-session.json
HEALTH_PATH=data/health.json
EOF
  fi
fi
sed -i 's#^X_SESSION_PATH=.*#X_SESSION_PATH=data/x-session.json#' .env 2>/dev/null || true

mkdir -p data
echo
echo "Worker ready."
echo "  Start it :  ./.venv/bin/python main.py"
echo "  Or via   :  sh run.sh start"