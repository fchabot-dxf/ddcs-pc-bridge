"""telemetry.py — WebSocket Command Center (optional telemetry broadcast).

Streams checkpoint/beacon events from the Fairy Gateway to any browser UI
that connects via WebSocket.  Uses a dedicated asyncio loop running in its
own daemon thread so it can coexist cleanly with the existing synchronous
http.server / threading architecture — no async migration needed.

Enabled with --ws (config.enable_ws = True).  Silently absent when
`websockets` is not installed, so the rest of the gateway keeps working.

Transport contract (all messages are JSON):
  {"type": "M3K_TELEMETRY",
   "event":      <"beacon"|"delivered"|"done"|"stalled"|"failed"|"heartbeat">,
   "checkpoint": <int beacon n, or null>,
   "job_id":     <str | null>,
   "name":       <filename | null>,
   "state":      <"running"|"delivered"|"done"|"stalled"|"failed"|null>,
   "variables":  {"last_beacon": n, "total": N, "percent": P},
   "timestamp":  <float unix epoch>}

Thread safety:
  broadcast() is safe to call from ANY thread (the sync Poller loop, the
  HTTP handler thread, etc.).  Internally it posts into the async loop via
  loop.call_soon_threadsafe, so the clients set is only ever touched from
  within that single async thread.
"""
import asyncio
import json
import logging
import threading
import time

log = logging.getLogger(__name__)

_OPTIONAL_IMPORT_ERR = None
try:
    import websockets                         # type: ignore
    import websockets.exceptions              # type: ignore
except ImportError as _e:                     # websockets not installed → graceful no-op
    websockets = None
    _OPTIONAL_IMPORT_ERR = str(_e)


class TelemetryServer:
    """Manage a WebSocket broadcast server in its own asyncio + daemon thread.

    Usage:
        ts = TelemetryServer()
        ts.start("0.0.0.0", 8766)          # returns immediately
        ts.broadcast({"type": "M3K_TELEMETRY", ...})  # thread-safe
        ts.stop()                           # graceful shutdown
    """

    def __init__(self):
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server = None                  # websockets server object
        self._clients: set = set()
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()      # set once the loop is running + server bound

    # ------------------------------------------------------------------
    # Public API (all thread-safe)
    # ------------------------------------------------------------------

    def start(self, host: str = "0.0.0.0", port: int = 8766):
        """Start the WebSocket server in a background daemon thread.
        Blocks until the server is bound (or import/bind failed).
        Returns self so callers can chain: ts = TelemetryServer().start(...)
        """
        if websockets is None:
            log.warning(
                "[telemetry] websockets package not installed (%s). "
                "WebSocket broadcast disabled — pip install websockets>=12",
                _OPTIONAL_IMPORT_ERR,
            )
            return self

        self._host = host
        self._port = port
        self._thread = threading.Thread(
            target=self._run_loop, name="telemetry-ws", daemon=True
        )
        self._thread.start()
        # Wait until the server is accepting connections (or startup failed)
        self._ready.wait(timeout=10.0)
        return self

    def broadcast(self, payload: dict):
        """Thread-safe: post a telemetry payload to all connected clients.
        Silently a no-op if the server isn't running or no clients are connected.
        """
        if self._loop is None or not self._loop.is_running():
            return
        self._loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(self._send_all(json.dumps(payload)),
                                          loop=self._loop)
        )

    def stop(self):
        """Signal the async loop to shut down.  Blocking until the thread exits."""
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=5.0)

    # ------------------------------------------------------------------
    # Internal async machinery (runs only inside the daemon thread)
    # ------------------------------------------------------------------

    def _run_loop(self):
        """Entry point for the daemon thread: creates the loop, starts the server."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            loop.run_until_complete(self._serve())
        except Exception as exc:
            log.error("[telemetry] startup error: %s", exc)
        finally:
            loop.close()
            self._loop = None

    async def _serve(self):
        """Bind the WebSocket server and run it until the loop stops."""
        try:
            server = await websockets.serve(
                self._handle_client, self._host, self._port
            )
            self._server = server
            log.info("[telemetry] WebSocket Command Center listening on ws://%s:%s",
                     self._host, self._port)
            self._ready.set()               # unblock TelemetryServer.start()
            await asyncio.get_event_loop().create_future()  # run forever
        except OSError as exc:
            log.error("[telemetry] bind failed on %s:%s — %s", self._host, self._port, exc)
            self._ready.set()              # unblock caller so it doesn't hang

    async def _handle_client(self, websocket):
        """Register a new client, keep the connection open, unregister on close."""
        self._clients.add(websocket)
        addr = websocket.remote_address
        log.debug("[telemetry] client connected: %s", addr)
        try:
            await websocket.wait_closed()
        finally:
            self._clients.discard(websocket)
            log.debug("[telemetry] client disconnected: %s", addr)

    async def _send_all(self, message: str):
        """Broadcast a message string to all currently-connected clients."""
        if not self._clients:
            return
        # Take a snapshot of the set so mutations during iteration are safe
        targets = list(self._clients)
        for ws in targets:
            try:
                await ws.send(message)
            except websockets.exceptions.ConnectionClosed:
                self._clients.discard(ws)
            except Exception as exc:
                log.debug("[telemetry] send error to %s: %s", ws.remote_address, exc)
                self._clients.discard(ws)


# ---------------------------------------------------------------------------
# Convenience: build a canonical M3K_TELEMETRY payload dict from Poller state
# ---------------------------------------------------------------------------

def make_checkpoint_payload(n: int, active: dict) -> dict:
    """Build the standard telemetry payload from a Poller beacon event.

    Args:
        n:      the beacon number just reached
        active: the Poller's `self.active` dict (may be None for heartbeats)
    """
    if active is None:
        return {
            "type": "M3K_TELEMETRY",
            "event": "heartbeat",
            "checkpoint": None,
            "job_id": None,
            "name": None,
            "state": None,
            "variables": {},
            "timestamp": time.time(),
        }

    m = active.get("map", {})
    total = active.get("total") or 0
    percent = 0.0
    # Find the percent from the beacon map if available
    beacons = m.get("beacons", [])
    for b in beacons:
        if b.get("n") == n:
            percent = float(b.get("percent", 0.0))
            break

    state = "running"
    if n >= total and total > 0:
        state = "done"

    return {
        "type": "M3K_TELEMETRY",
        "event": "beacon",
        "checkpoint": n,
        "job_id": active.get("job_id"),
        "name": active.get("name"),
        "state": state,
        "variables": {
            "last_beacon": n,
            "total": total,
            "percent": percent,
        },
        "timestamp": time.time(),
    }


def make_state_payload(event: str, active: dict | None) -> dict:
    """Build a state-change payload (delivered / done / stalled / failed)."""
    return {
        "type": "M3K_TELEMETRY",
        "event": event,
        "checkpoint": active.get("last_beacon") if active else None,
        "job_id": active.get("job_id") if active else None,
        "name": active.get("name") if active else None,
        "state": event,
        "variables": {},
        "timestamp": time.time(),
    }
