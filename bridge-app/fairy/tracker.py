"""tracker.py — pure function: (map, last_beacon, state) -> status object (PROTOCOL §5).

No side effects. The Poller hands the result to Backend.put_status. A bare beacon number
becomes percent / op / line / ETA via the per-job map (PROTOCOL §2).
"""
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def beacon_for(m, n):
    """Look up beacon n in the map (beacons are 1-based; list is usually [n-1] but we search
    to be robust to gaps)."""
    if not n:
        return None
    for b in m.get("beacons", []):
        if b.get("n") == n:
            return b
    return None


def build_status(job_id, name, m, state, last_beacon, events):
    total_t = m.get("total_est_time_s")
    percent = 0.0
    op = None
    line = None
    eta = round(total_t) if isinstance(total_t, (int, float)) else None

    b = beacon_for(m, last_beacon)
    if b:
        if isinstance(b.get("percent"), (int, float)):
            percent = b["percent"]
        op = b.get("op")
        line = b.get("orig_line")
        if isinstance(total_t, (int, float)) and isinstance(b.get("cum_time_s"), (int, float)):
            eta = max(0, round(total_t - b["cum_time_s"]))

    return {
        "jobId": job_id,
        "name": name,
        "state": state,
        "last_beacon": last_beacon,
        "total_beacons": m.get("total_beacons"),
        "percent": percent,
        "op": op,
        "line": line,
        "eta_s": eta,
        "updated_at": _now(),
        "events": list(events),
    }
