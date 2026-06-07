"""ops.py — the API-first operations surface (CONFIGS §8).

Every capability is a plain method here, so the operations have ONE definition reused by every caller:
the local HTTP server (server.py), and later an MCP agent server or an embedded client. The console UI
is just one consumer. Keeping this layer thin + caller-agnostic is what makes "AI agent (MCP)" and
"portable into another app" free later.

These run ON the gateway, so file actions execute directly (backend + cncdisk). (In the *cloud* config the
console can't reach the gateway directly, so it writes to R2 and the gateway's poll loop picks it up —
same end calls, different trigger.)
"""
import datetime
import re

from . import __version__, cncdisk, identity

_SLUG = re.compile(r"[^A-Za-z0-9_.-]+")


def make_job_id(name, now=None):
    """`<YYYYMMDDTHHMMSS>-<slug>` — lexicographically sortable = FIFO creation order (PROTOCOL §3)."""
    now = now or datetime.datetime.now()
    base = name.rsplit(".", 1)[0] if "." in name else name
    slug = _SLUG.sub("_", base).strip("_") or "job"
    return f"{now.strftime('%Y%m%dT%H%M%S')}_{now.microsecond:06d}-{slug}"


class Ops:
    def __init__(self, backend, config):
        self.backend = backend
        self.cfg = config

    # --- jobs ---------------------------------------------------------------
    def submit_job(self, name, nc, mapping=None):
        """Queue a job. nc = G-code (str or bytes). mapping present => tracked; absent => deliver-only."""
        job_id = make_job_id(name)
        self.backend.put_job(job_id, nc, mapping)
        tracked = bool(mapping and mapping.get("total_beacons"))
        return {"jobId": job_id, "name": name, "tracked": tracked}

    def list_queue(self):
        """The queue/tracker view: every status object, plus inbox jobs not yet given a status."""
        statuses = {s.get("jobId"): s for s in self.backend.list_statuses()}
        items = list(statuses.values())
        for jid in self.backend.list_inbox():
            if jid not in statuses:
                items.append({"jobId": jid, "state": "queued"})
        items.sort(key=lambda s: s.get("jobId", ""))
        return items

    def get_status(self, job_id):
        return self.backend.get_status(job_id)

    def list_history(self, limit=100):
        """Finished-job history: name, final state, duration (History view seam)."""
        return self.backend.list_history(limit)

    # --- CNCDISK files ------------------------------------------------------
    def list_files(self):
        return cncdisk.build_index(self.cfg.expert_dest)

    def delete_file(self, name):
        return cncdisk.apply_command(self.cfg.expert_dest, {"op": "delete", "target": name})

    def read_file(self, name):
        """Read one CNCDISK file's text (G-code text view seam). Same target validation as delete."""
        import os
        if not name or os.path.basename(name) != name:
            return {"ok": False, "error": f"invalid target: {name!r}"}
        full = os.path.join(self.cfg.expert_dest, name)
        if not os.path.isfile(full):
            return {"ok": False, "error": f"not found: {name}"}
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                return {"ok": True, "name": name, "content": f.read()}
        except OSError as e:
            return {"ok": False, "error": str(e)}

    # --- identity / descriptor ---------------------------------------------
    def controller_reachable(self):
        import os
        try:
            return os.path.isdir(self.cfg.expert_dest)
        except OSError:
            return False

    def descriptor(self):
        """Who this gateway is + its live-ish state. Basis for the heartbeat and the Admin view."""
        found = identity.read(self.cfg.expert_dest, self.cfg.identity_filename)
        return {
            "machine_id": self.cfg.machine_id,
            "machine_name": self.cfg.machine_name,
            "controller_id": found.get("id") if found else None,
            "controller_name": found.get("name") if found else None,
            "controller_connected": self.controller_reachable(),
            "dest": self.cfg.expert_dest,            # which controller disk this gateway is pointed at
            "backend": self.cfg.backend,
            "version": __version__,
        }
