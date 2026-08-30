"""Small adapter between Telegram messages and tweetkit-x."""

import json
from pathlib import Path

from tweetkit_x import TweetKit
from tweetkit_x.cookie import build_cookie_string


class XPublisher:
    def __init__(self, session_path: Path) -> None:
        self.session_path = session_path
        self._session_mtime_ns = 0
        self.client = None
        self.user_id = None
        self.reload()

    def reload(self) -> None:
        session_path = self.session_path
        if not session_path.is_file():
            raise FileNotFoundError(f"X session file not found: {session_path}")

        raw_session = session_path.read_text(encoding="utf-8").strip()
        try:
            cookies = json.loads(raw_session)
        except json.JSONDecodeError:
            cookie_string = raw_session
        else:
            if not isinstance(cookies, dict):
                raise ValueError("X session JSON must contain a flat cookie object.")
            cookie_string = build_cookie_string(cookies)

        self.client = TweetKit(cookie=cookie_string)
        self.user_id = self.client.whoami().get("user_id")
        self._session_mtime_ns = session_path.stat().st_mtime_ns

    def reload_if_changed(self) -> bool:
        current = self.session_path.stat().st_mtime_ns
        if current == self._session_mtime_ns:
            return False
        self.reload()
        return True

    def post(self, text: str, image_path: str | None = None) -> dict:
        self.reload_if_changed()
        text = text.strip()
        if not text and not image_path:
            return {"ok": False, "error": "Message has no text or image."}
        if len(text) > 280:
            return {
                "ok": False,
                "error": f"Message is {len(text)} characters; X limit is 280.",
            }
        return self.client.post(text, image_path=image_path)
