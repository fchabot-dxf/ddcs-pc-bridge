"""server.py — the gateway's LOCAL HTTP server (CONFIGS §3 offline/local configs).

Exposes the Ops surface (ops.py) as a small JSON API and serves the static console at `/`.
This is how the gateway *serves the console* at localhost (offline) or on the LAN (local-network):
download the gateway, run it, open the browser → the whole local system.

Stdlib only (http.server) — no extra dependency, works fully offline. Binds 127.0.0.1 by default
(offline/one-box); set host=0.0.0.0 for the local-network config. CORS is permissive so the console
can also be opened from a separate dev origin during development.

API (all JSON):
  GET  /api/descriptor                 -> gateway descriptor (machine id/name, controller_connected, ...)
  GET  /api/queue                      -> [ status/queue items ]
  GET  /api/status?id=<jobId>          -> one status object (404 if none)
  GET  /api/files                      -> CNCDISK listing (cncdisk/index shape)
  GET  /api/file?name=<file>           -> { ok, name, content }  (read a CNCDISK file)
  POST /api/jobs        {name, nc, map?}-> { jobId, name, tracked }   (queue a job)
  POST /api/files/delete{name}         -> { ok, ... }                 (safe delete on CNCDISK)
"""
import json
import mimetypes
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

_PLACEHOLDER = (
    b"<!doctype html><meta charset=utf-8><title>DDCS Bridge gateway</title>"
    b"<body style='font:14px system-ui;margin:3em;max-width:40em'>"
    b"<h2>DDCS Bridge \xe2\x80\x94 gateway running</h2>"
    b"<p>The console isn't bundled yet. The operations API is live under "
    b"<code>/api/</code> (e.g. <a href='/api/descriptor'>/api/descriptor</a>, "
    b"<a href='/api/queue'>/api/queue</a>, <a href='/api/files'>/api/files</a>).</p>"
)


class _Handler(BaseHTTPRequestHandler):
    server_version = "ddcs-bridge-gateway"

    # -- helpers --------------------------------------------------------------
    def _send_json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def log_message(self, *a):  # keep the gateway log clean
        pass

    @property
    def ops(self):
        return self.server.ops

    # -- routing --------------------------------------------------------------
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        path, q = u.path, parse_qs(u.query)
        if path == "/api/descriptor":
            return self._send_json(self.ops.descriptor())
        if path == "/api/config":
            return self._send_json(self.ops.get_config())
        if path == "/api/queue":
            return self._send_json(self.ops.list_queue())
        if path == "/api/history":
            try:
                limit = int((q.get("limit") or ["100"])[0])
            except ValueError:
                limit = 100
            return self._send_json(self.ops.list_history(limit))
        if path == "/api/status":
            st = self.ops.get_status((q.get("id") or [""])[0])
            return self._send_json(st, 200) if st else self._send_json({"error": "no such job"}, 404)
        if path == "/api/files":
            return self._send_json(self.ops.list_files())
        if path == "/api/file":
            return self._send_json(self.ops.read_file((q.get("name") or [""])[0]))
        return self._serve_static(path)

    def do_POST(self):
        if self.path == "/api/jobs":
            b = self._read_body()
            if not b.get("name") or "nc" not in b:
                return self._send_json({"error": "name and nc required"}, 400)
            return self._send_json(self.ops.submit_job(b["name"], b["nc"], b.get("map")))
        if self.path == "/api/files/delete":
            b = self._read_body()
            return self._send_json(self.ops.delete_file(b.get("name", "")))
        if self.path == "/api/config":
            return self._send_json(self.ops.set_config(self._read_body()))
        return self._send_json({"error": "not found"}, 404)

    # -- static console -------------------------------------------------------
    def _serve_static(self, path):
        root = self.server.console_dir
        if not root:
            return self._send_bytes(_PLACEHOLDER, "text/html")
        rel = path.lstrip("/") or "index.html"
        full = os.path.normpath(os.path.join(root, rel))
        if not full.startswith(os.path.normpath(root)) or not os.path.isfile(full):
            return self._send_json({"error": "not found"}, 404)
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        with open(full, "rb") as f:
            self._send_bytes(f.read(), ctype)

    def _send_bytes(self, body, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def start_server(config, ops):
    """Start the local HTTP server in a daemon thread. Returns the server (call .shutdown() to stop)."""
    httpd = ThreadingHTTPServer((config.host, config.port), _Handler)
    httpd.ops = ops
    httpd.console_dir = config.console_dir
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd
