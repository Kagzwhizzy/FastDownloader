"""Tiny local listener so the Chrome extension can hand links to the app.

It only listens on 127.0.0.1 (this PC), never on the internet. Requests must carry the
X-FastDL header; web pages cannot add that header without a CORS pre-flight, which we refuse,
so random websites cannot push downloads into the app.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests
from PySide6.QtCore import QObject, Signal

from . import config


class Bridge(QObject):
    download_requested = Signal(dict)
    video_requested = Signal(dict)
    show_requested = Signal()

    def __init__(self):
        super().__init__()
        self.server = None

    def start(self):
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _ok(self, obj=None, code=200):
                body = json.dumps(obj or {"ok": True}).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _allowed(self):
                return self.headers.get("X-FastDL") == "1"

            def do_OPTIONS(self):  # refuse CORS pre-flight -> websites can't call us
                self.send_response(403)
                self.end_headers()

            def do_GET(self):
                if not self._allowed():
                    return self._ok({"ok": False}, 403)
                if self.path == "/ping":
                    return self._ok({"ok": True, "app": config.APP_NAME, "version": config.VERSION})
                self._ok({"ok": False}, 404)

            def do_POST(self):
                if not self._allowed():
                    return self._ok({"ok": False}, 403)
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                    data = json.loads(self.rfile.read(min(n, 1_000_000)) or b"{}")
                except Exception:
                    return self._ok({"ok": False}, 400)
                if self.path == "/probe" and data.get("url"):
                    # extension asks: can the app download this link? (before it cancels the browser download)
                    from . import engine
                    try:
                        info = engine.probe(data["url"], headers_from(data), timeout=15)
                        return self._ok({"ok": True, "info": info})
                    except Exception as e:  # noqa: BLE001
                        return self._ok({"ok": False, "error": str(e)[:200]})
                if self.path == "/download" and data.get("url"):
                    bridge.download_requested.emit(data)
                elif self.path == "/video" and (data.get("pageUrl") or data.get("direct")):
                    bridge.video_requested.emit(data)
                elif self.path == "/show":
                    bridge.show_requested.emit()
                else:
                    return self._ok({"ok": False}, 404)
                self._ok()

        self.server = ThreadingHTTPServer(("127.0.0.1", config.PORT), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        if self.server:
            self.server.shutdown()


def headers_from(data):
    """Browser details sent by the extension, so the server sees the same 'person' as in the browser."""
    h = {}
    if data.get("referrer"):
        h["Referer"] = data["referrer"]
    if data.get("cookie"):
        h["Cookie"] = data["cookie"]
    if data.get("ua"):
        h["User-Agent"] = data["ua"]
    return h


def ask_running_instance_to_show():
    """If the app is already open, bring that window up instead of opening a second copy."""
    try:
        requests.post(f"http://127.0.0.1:{config.PORT}/show", headers={"X-FastDL": "1"}, json={}, timeout=2)
        return True
    except Exception:
        return False
