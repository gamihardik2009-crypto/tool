"""Private credential upload API; bind it to the VPS Tailscale address."""
from __future__ import annotations
import hmac, json, os, signal, tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TOKEN = os.environ.get("TELEGRAM_X_SYNC_TOKEN", "")
SESSION = Path(os.environ.get("X_SESSION_PATH", "data/x-session.json"))

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        return
    def do_GET(self):
        if self.path != "/health": self.send_error(404); return
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b'{"ok":true}')
    def do_POST(self):
        if self.path != "/v1/session": self.send_error(404); return
        supplied = self.headers.get("Authorization", "")
        if not TOKEN or not hmac.compare_digest(supplied, "Bearer " + TOKEN): self.send_error(401, "Authentication failed"); return
        try:
            length = int(self.headers.get("Content-Length", "0")); payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict) or not payload.get("auth_token") or not payload.get("ct0"): raise ValueError
            SESSION.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix=".x-session-", dir=str(SESSION.parent)); os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f: json.dump(payload, f)
            os.replace(tmp, SESSION); self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b'{"ok":true}')
        except Exception: self.send_error(400, "Invalid credential payload")

if __name__ == "__main__":
    if not TOKEN: raise SystemExit("TELEGRAM_X_SYNC_TOKEN is required")
    bind = os.environ.get("SYNC_BIND", "127.0.0.1"); port = int(os.environ.get("SYNC_PORT", "8787"))
    ThreadingHTTPServer((bind, port), Handler).serve_forever()
