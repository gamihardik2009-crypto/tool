#!/usr/bin/env bash
set -euo pipefail

BASE="${XDG_DATA_HOME:-$HOME/.local/share}/telegram-x-manager"
REPO="https://github.com/gamihardik2009-crypto/tool.git"
BIN="${XDG_BIN_HOME:-$HOME/.local/bin}"

if [ ! -d "$BASE/.git" ]; then
  mkdir -p "$(dirname "$BASE")"
  git clone "$REPO" "$BASE"
else
  git -C "$BASE" pull --ff-only
fi

cd "$BASE/manager"
"${PYTHON:-python3}" -m venv .venv
"$BASE/manager/.venv/bin/python" -m pip install --upgrade pip >/dev/null
"$BASE/manager/.venv/bin/python" -m pip install -e . >/dev/null

mkdir -p "$BIN"
cat > "$BIN/X" <<EOF
#!/usr/bin/env bash
exec "$BASE/manager/.venv/bin/telegram-x-manager" tui "\$@"
EOF
chmod 755 "$BIN/X"

case ":${PATH}:" in
  *":$BIN:"*) ;;
  *) echo "Add this directory to PATH, then restart your terminal: $BIN" ;;
esac
echo "Installed. Start the manager from anywhere with: X"
