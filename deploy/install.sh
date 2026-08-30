#!/bin/sh
set -eu

APP_DIR=/opt/telegram-x
CONFIG_DIR=/etc/telegram-x
STATE_DIR=/var/lib/telegram-x

id telegram-x >/dev/null 2>&1 || useradd --system --home "$STATE_DIR" --shell /usr/sbin/nologin telegram-x
mkdir -p "$APP_DIR" "$CONFIG_DIR" "$STATE_DIR"
chown -R telegram-x:telegram-x "$APP_DIR" "$STATE_DIR"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"
PLAYWRIGHT_BROWSERS_PATH="$APP_DIR/browsers" \
    "$APP_DIR/.venv/bin/playwright" install --with-deps chromium
chown -R telegram-x:telegram-x "$APP_DIR/browsers"
install -m 0644 "$APP_DIR/deploy/telegram-x.service" /etc/systemd/system/telegram-x.service
install -m 0644 "$APP_DIR/deploy/telegram-x-session.service" /etc/systemd/system/telegram-x-session.service
systemctl daemon-reload
systemctl enable telegram-x.service telegram-x-session.service
