"""poller.py — the heart: the single-active-job state machine (PROTOCOL §4).

Because the beacon frame carries no job id, only ONE job is active (running + tracked) at
a time. The poller serializes the queue:

  idle  : LIST inbox -> claim oldest -> Transfer to Expert -> DELETE from inbox -> "delivered"
            - TRACKED job (has a map w/ beacons): becomes active and is watched (below).
            - DELIVER-ONLY job (no map, e.g. a probe): "delivered" is terminal; slot stays free.
  active: watch the beacon source; each new valid n -> "running" + status update
          last beacon (complete) -> "done", free the slot
          no new beacon for stall_seconds -> "stalled", free the slot

No retention: the inbox/ entry is deleted the instant delivery succeeds (the bytes are now on
the controller and the map is held in memory for tracking). So inbox/ is a pure delivery queue
that holds a job only for the seconds between submit and pickup; live tracking runs off the
in-memory map + the status/ object. A crashed/restarted fairy therefore can't re-deliver a job
to a controller that's mid-cut.

One tick = one iteration. bridge.py calls tick() on a timer.
"""
import time

from . import identity, tracker


class Poller:
    def __init__(self, backend, transfer, beacons, config, log=print):
        self.backend = backend
        self.transfer = transfer
        self.beacons = beacons
        self.cfg = config
        self.log = log
        self.active = None     # None when idle; else the active-job dict

    # -- one iteration --------------------------------------------------------
    def tick(self):
        if self.active is None:
            self._maybe_claim()
        else:
            self._watch()

    # -- idle: pick up the next job ------------------------------------------
    def _maybe_claim(self):
        ids = self.backend.list_inbox()
        if ids:
            self._claim(ids[0])                    # oldest jobId == FIFO

    def _claim(self, job_id):
        nc, m = self.backend.get_job(job_id)
        name = self._job_name(job_id, m)
        tracked = bool(m.get("total_beacons"))     # has a map with beacons -> Fusion cut; else deliver-only
        self.beacons.reset(m.get("marker") or 111)  # per-job marker; forget the previous job's beacons (§4)
        events = [f"claimed {job_id}"]

        # safety: never deliver to the wrong controller (CONFIGS §7). Skipped if no machine_id configured.
        ok, reason = identity.verify(self.cfg.expert_dest, self.cfg.identity_filename, self.cfg.machine_id)
        if not ok:
            self.log(f"[poller] REFUSED {job_id}: {reason}")
            self.backend.put_status(
                job_id, tracker.build_status(job_id, name, m, "failed", 0, events + [f"refused: {reason}"]))
            self.backend.delete_job(job_id)
            return

        try:
            dest = self.transfer.deliver(nc, name)
        except OSError as e:
            self.log(f"[poller] DELIVERY FAILED {job_id}: {e}")
            self.backend.put_status(
                job_id, tracker.build_status(job_id, name, m, "failed", 0, events + [f"delivery failed: {e}"]))
            self.backend.delete_job(job_id)        # don't wedge the queue on a bad job
            return
        self.backend.delete_job(job_id)            # delivered -> bucket copy no longer needed (controller has it)
        if not tracked:
            # deliver-only (probe / utility .nc): no beacons to watch; "delivered" is terminal
            self.backend.put_status(
                job_id, tracker.build_status(job_id, name, m, "delivered", 0,
                                             events + [f"delivered (deliver-only) -> {dest}"]))
            self.log(f"[poller] delivered (deliver-only) {name} ({job_id})")
            return
        now = time.time()
        self.active = {
            "job_id": job_id, "name": name, "map": m,
            "total": m.get("total_beacons"),
            "last_beacon": 0, "events": events + [f"delivered -> {dest}"],
            "last_progress_at": now,
        }
        self.log(f"[poller] delivered {name} ({job_id}) -> awaiting Cycle Start + beacons")
        self._put("delivered")

    @staticmethod
    def _job_name(job_id, m):
        """Filename to deliver under. Prefer the map's source; else strip the jobId's timestamp
        prefix (`<ts>-<name>` -> `<name>.nc`)."""
        if m.get("source"):
            return m["source"]
        base = job_id.split("-", 1)[1] if "-" in job_id else job_id
        return base + ".nc"

    # -- active: watch beacons -----------------------------------------------
    def _watch(self):
        a = self.active
        now = time.time()
        latest = self.beacons.latest()
        if latest is not None and latest[0] > a["last_beacon"]:
            n, ts = latest
            a["last_beacon"] = n
            a["last_progress_at"] = ts
            a["events"].append(f"beacon {n}/{a['total']}")
            self.log(f"[poller] {a['name']}: beacon {n}/{a['total']}")
            if self._is_complete(a, n):
                a["events"].append("done")
                self._put("done")                  # inbox copy already deleted at delivery
                self.log(f"[poller] {a['name']}: DONE")
                self.active = None
            else:
                self._put("running")
            return

        # no new beacon: check for a stall
        if now - a["last_progress_at"] > self.cfg.stall_seconds:
            where = f"after beacon {a['last_beacon']}" if a["last_beacon"] else "after delivery (no Start?)"
            a["events"].append(f"stalled {where}")
            self._put("stalled")                   # inbox copy already deleted at delivery
            self.log(f"[poller] {a['name']}: STALLED {where}")
            self.active = None

    # -- helpers --------------------------------------------------------------
    def _is_complete(self, a, n):
        b = tracker.beacon_for(a["map"], n)
        if b and b.get("complete"):
            return True
        return a["total"] is not None and n >= a["total"]

    def _put(self, state):
        a = self.active
        self.backend.put_status(
            a["job_id"],
            tracker.build_status(a["job_id"], a["name"], a["map"], state, a["last_beacon"], a["events"]),
        )
