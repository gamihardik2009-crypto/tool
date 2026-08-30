#!/bin/sh
# Portable background launcher for the Telegram→X worker. Works without systemd
# (Termux, plain VPS, containers). Uses a pid file + nohup log.
#   Use:  sh run.sh start | stop | status
set -eu
cd "$(dirname "$0")"

PID_FILE="$PWD/data/worker.pid"
LOG_FILE="$PWD/data/collector.log"
action="${1:-status}"

is_running() {
  [ -f "$PID_FILE" ] || return 1
  pid=$(cat "$PID_FILE" 2>/dev/null)
  [ -n "$pid" ] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  # Make sure the pid was not recycled by some other process.
  if [ -r "/proc/$pid/cmdline" ]; then
    grep -q "main.py" "/proc/$pid/cmdline" 2>/dev/null || return 1
  fi
  return 0
}

case "$action" in
  start)
    if is_running; then
      echo "Worker already running (pid $(cat "$PID_FILE"))."
      exit 0
    fi
    mkdir -p "$PWD/data"
    # Best effort: keep Android from freezing the process (Termux only).
    command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock 2>/dev/null || true
    nohup "$PWD/.venv/bin/python" "$PWD/main.py" </dev/null >>"$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "Worker started (pid $(cat "$PID_FILE")). Log: $LOG_FILE"
    ;;
  stop)
    if is_running; then
      kill "$(cat "$PID_FILE")" 2>/dev/null || true
      sleep 1
      rm -f "$PID_FILE"
      echo "Worker stopped."
    else
      rm -f "$PID_FILE"
      echo "Worker not running."
    fi
    ;;
  status)
    if is_running; then
      echo "running (pid $(cat "$PID_FILE"))"
    else
      echo "not running"
    fi
    ;;
  logs)
    n="${2:-50}"
    tail -n "$n" "$LOG_FILE" 2>/dev/null || echo "no log yet"
    ;;
  *)
    echo "usage: sh run.sh {start|stop|status|logs [n]}"
    exit 1
    ;;
esac