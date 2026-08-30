from __future__ import annotations

import curses
import subprocess
import sys
import time


OPTIONS = [
    ("Health", ["health"]),
    ("Activity history", ["history"]),
    ("Telegram credentials", ["creds"]),
    ("X browser login", ["xlogin"]),
    ("Connect SSH", ["connect"]),
    ("Deploy worker", ["deploy"]),
    ("Worker status", ["control", "status"]),
    ("Worker logs", ["control", "logs"]),
    ("Stop worker", ["control", "stop"]),
    ("Start worker", ["control", "start"]),
    ("Quit", None),
]


def _run(stdscr, label: str, argv: list[str]) -> str:
    proc = subprocess.Popen([sys.executable, "-m", "telegram_x_manager", *argv],
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    started = time.monotonic()
    frames = "|/-\\"
    while proc.poll() is None:
        elapsed = int(time.monotonic() - started)
        stdscr.erase()
        stdscr.addstr(0, 0, "Telegram-X Manager", curses.A_BOLD)
        stdscr.addstr(2, 2, f"{frames[elapsed % len(frames)]} {label} is running... ({elapsed}s)")
        stdscr.addstr(4, 2, "Network operations can take a few seconds. Please wait.")
        stdscr.refresh()
        time.sleep(0.2)
    output = proc.stdout.read() if proc.stdout else ""
    return output.strip() or f"Command exited with {proc.returncode}."


def _run_interactive(stdscr, argv: list[str]) -> str:
    """Run a prompt-driven command with the terminal returned to the user."""
    curses.endwin()
    try:
        proc = subprocess.run([sys.executable, "-m", "telegram_x_manager", *argv],
                              text=True)
        return f"Command finished (exit {proc.returncode})."
    finally:
        stdscr.clear()
        stdscr.refresh()


def _page(stdscr, title: str, body: str) -> None:
    stdscr.erase()
    stdscr.addstr(0, 0, title[: curses.COLS - 1], curses.A_BOLD)
    lines = body.splitlines() or [""]
    for row, line in enumerate(lines[: curses.LINES - 3], 2):
        stdscr.addstr(row, 0, line[: curses.COLS - 1])
    stdscr.addstr(curses.LINES - 1, 0, "Press any key to return"[: curses.COLS - 1])
    stdscr.refresh()
    stdscr.getch()


def _main(stdscr) -> None:
    curses.curs_set(0)
    selected = 0
    while True:
        stdscr.erase()
        stdscr.addstr(0, 0, "Telegram-X Manager", curses.A_BOLD)
        stdscr.addstr(1, 0, "Use arrows, Enter to select, q to quit")
        for idx, (label, _) in enumerate(OPTIONS):
            attr = curses.A_REVERSE if idx == selected else curses.A_NORMAL
            stdscr.addstr(idx + 3, 2, label[: curses.COLS - 3], attr)
        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), ord("Q")):
            return
        if key == curses.KEY_UP:
            selected = (selected - 1) % len(OPTIONS)
        elif key == curses.KEY_DOWN:
            selected = (selected + 1) % len(OPTIONS)
        elif key in (curses.KEY_ENTER, 10, 13):
            label, command = OPTIONS[selected]
            if command is None:
                return
            curses.curs_set(1)
            if command[0] in ("connect", "creds", "xlogin"):
                result = _run_interactive(stdscr, command)
            else:
                result = _run(stdscr, label, command)
            _page(stdscr, label, result)
            curses.curs_set(0)


def run() -> int:
    curses.wrapper(_main)
    return 0
