"""cncdisk.py — the CNCDISK file explorer (PROTOCOL §7).

fairy is the only PC cabled to the controller, so it publishes a listing of the Expert's CNCDISK
to the rendezvous (`cncdisk/index.json`) for the web Files tab, and processes file-management
**commands** the web app drops in `commands/`.

⚠️ This is the first web → controller action. Safety is enforced HERE, on fairy:
  * Op allowlist = {"delete"} ONLY — never anything that runs/starts G-code.
  * Target must be a bare filename that already exists on CNCDISK (no path traversal).
  * The web Worker's token gates who can write `commands/`; fairy logs every command it executes.

Operates on the same directory `transfer` delivers to (config.expert_dest) via plain file ops,
which work over the SMB UNC path exactly as they do on a local folder (so it's testable offline).
"""
import os
import time

SAFE_OPS = {"delete"}


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def list_dir(path):
    files = []
    for name in os.listdir(path):
        full = os.path.join(path, name)
        if os.path.isfile(full):
            st = os.stat(full)
            files.append({"name": name, "size": st.st_size, "mtime": int(st.st_mtime)})
    return sorted(files, key=lambda f: f["name"])


def build_index(path):
    """Listing of CNCDISK. Never raises — an unreachable controller becomes an index with an error."""
    try:
        return {"path": path, "files": list_dir(path), "updated_at": _now()}
    except OSError as e:
        return {"path": path, "files": [], "error": str(e), "updated_at": _now()}


def apply_command(path, cmd):
    """Validate + execute one command against CNCDISK. Returns a result dict; never raises on a
    bad/disallowed command (so a poisoned command can't wedge the loop)."""
    op = cmd.get("op")
    if op not in SAFE_OPS:
        return {"ok": False, "error": f"op not allowed: {op!r}"}
    target = cmd.get("target", "")
    # bare filename only — reject path traversal / nested paths
    if not target or os.path.basename(target) != target:
        return {"ok": False, "error": f"invalid target: {target!r}"}
    full = os.path.join(path, target)
    if not os.path.isfile(full):
        return {"ok": False, "error": f"not found: {target}"}
    try:
        os.remove(full)
    except OSError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "op": op, "target": target}


class CncDiskService:
    """Per-tick: process any pending commands, then republish the listing on a cadence."""

    def __init__(self, backend, path, refresh_s=15.0, log=print):
        self.backend = backend
        self.path = path
        self.refresh_s = refresh_s
        self.log = log
        self._last_index = 0.0

    def tick(self, now=None):
        now = time.time() if now is None else now
        changed = self._process_commands()
        if changed or (now - self._last_index) >= self.refresh_s:
            self.publish()
            self._last_index = now

    def publish(self):
        self.backend.put_cncdisk_index(build_index(self.path))

    def _process_commands(self):
        changed = False
        for cmd_id, cmd in self.backend.list_commands():
            result = apply_command(self.path, cmd)
            level = "ok" if result.get("ok") else "REJECTED"
            self.log(f"[cncdisk] command {cmd_id} {cmd}: {level} {result}")
            self.backend.clear_command(cmd_id)     # processed (good or bad) -> never re-run
            changed = changed or result.get("ok", False)
        return changed
