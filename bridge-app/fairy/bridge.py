"""bridge.py — fairy entry point (ARCHITECTURE.md §4). Wires the modules and runs the loop.

  python -m fairy.bridge --self-test            # offline logic checks (no hardware/cloud)
  python -m fairy.bridge --demo                 # full pipeline on a temp LocalFolder, sim beacons
  python -m fairy.bridge run                    # real: ModbusBeaconSource + SMB, loop forever
      [--backend local|r2] [--root DIR] [--dest PATH] [--port COM6] [--baud 115200]
      [--slave 1] [--stall 120] [--poll 5]

Run from the bridge-app/ directory so `fairy` is importable as a package.
"""
import argparse
import sys
import time

from .backend import make_backend
from .cncdisk import CncDiskService
from .config import Config
from .poller import Poller
from .slave import ModbusBeaconSource, SimBeaconSource
from .transfer import Transfer


def build(config, beacons=None):
    backend = make_backend(config)
    transfer = Transfer(config.expert_dest)
    if beacons is None:
        beacons = ModbusBeaconSource(config.com_port, config.baud, config.slave_id)
    poller = Poller(backend, transfer, beacons, config)
    return backend, transfer, beacons, poller


def run_loop(config):
    backend, _, beacons, poller = build(config)
    explorer = CncDiskService(backend, config.expert_dest, config.cncdisk_refresh_s)
    beacons.start()
    explorer.publish()                          # publish an initial CNCDISK listing at startup
    print(f"[bridge] up — backend={config.backend}  dest={config.expert_dest}  "
          f"slave={config.com_port}@{config.baud}")
    print("[bridge] polling… (Ctrl+C to stop)")
    try:
        while True:
            poller.tick()
            explorer.tick()
            time.sleep(config.run_poll_interval_s if poller.active else config.poll_interval_s)
    except KeyboardInterrupt:
        print("\n[bridge] stopped")


# --------------------------------------------------------------------------- demo
def _seed_demo_job(backend, job_id):
    """Write a small instrumented job + map into inbox/ (shape per PROTOCOL §2)."""
    import json
    import os
    nc = "(demo bracket)\n#251 = 111\n#250 = 1\nMSETDATA[250,1,0,2,16,300]\nM30\n"
    m = {
        "source": "demo_bracket.nc",
        "var": 250, "marker_var": 251, "marker": 111,
        "msetdata": "MSETDATA[250,1,0,2,16,300]",
        "total_est_time_s": 40.0,
        "total_beacons": 4,
        "beacons": [
            {"n": 1, "orig_line": 12, "op": "2D Contour1", "cum_time_s": 10.0, "percent": 25.0, "complete": False},
            {"n": 2, "orig_line": 40, "op": "2D Contour2", "cum_time_s": 20.0, "percent": 50.0, "complete": False},
            {"n": 3, "orig_line": 70, "op": "Drill 6mm", "cum_time_s": 30.0, "percent": 75.0, "complete": False},
            {"n": 4, "orig_line": 99, "op": "Finish", "cum_time_s": 40.0, "percent": 100.0, "complete": True},
        ],
    }
    with open(os.path.join(backend.inbox, job_id + ".nc"), "w", encoding="utf-8") as f:
        f.write(nc)
    with open(os.path.join(backend.inbox, job_id + ".map.json"), "w", encoding="utf-8") as f:
        json.dump(m, f, indent=2)


def demo():
    """Full pipeline on a throwaway folder with simulated beacons — no hardware, no cloud."""
    import json
    import os
    import tempfile
    root = tempfile.mkdtemp(prefix="fairy_demo_")
    dest = os.path.join(root, "cncdisk")              # stands in for \\192.168.0.99\CNCDISK
    cfg = Config(backend="local", local_root=root, expert_dest=dest,
                 poll_interval_s=0.1, run_poll_interval_s=0.1, stall_seconds=5.0)
    beacons = SimBeaconSource()
    backend, transfer, _, poller = build(cfg, beacons=beacons)

    print(f"[demo] root = {root}")
    _seed_demo_job(backend, "20260607T120000-demo_bracket")

    poller.tick()                                     # claim + deliver
    assert poller.active, "expected a job to be claimed"
    print(f"[demo] delivered to CNCDISK: {os.listdir(dest)}")

    for n in (1, 2, 3, 4):
        beacons.feed(n)                               # controller 'reaches' beacon n
        poller.tick()
        time.sleep(0.05)

    job_id = "20260607T120000-demo_bracket"
    with open(os.path.join(backend.status, job_id + ".json"), encoding="utf-8") as f:
        st = json.load(f)
    print("[demo] final status:")
    print(json.dumps(st, indent=2))
    assert st["state"] == "done" and st["percent"] == 100.0, "demo did not reach done/100%"
    assert job_id not in backend.list_inbox(), "job should be gone from inbox (no retention)"
    assert poller.active is None, "slot should be free after done"
    print("\n[demo] OK — submit -> deliver -> beacons -> done, end to end (G-code not retained).")
    return 0


# --------------------------------------------------------------------------- self-test
def self_test():
    import json
    import os
    import tempfile

    ok = True

    def check(cond, label):
        nonlocal ok
        print(f"  [{'ok' if cond else 'FAIL'}] {label}")
        ok = ok and cond

    def fresh(stall=120.0):
        root = tempfile.mkdtemp(prefix="fairy_test_")
        dest = os.path.join(root, "cncdisk")
        cfg = Config(backend="local", local_root=root, expert_dest=dest, stall_seconds=stall)
        beacons = SimBeaconSource()
        backend, _, _, poller = build(cfg, beacons=beacons)
        return root, backend, beacons, poller

    def seed(backend, job_id="20260607T000000-job"):
        _seed_demo_job(backend, job_id)
        return job_id

    def status(backend, job_id):
        with open(os.path.join(backend.status, job_id + ".json"), encoding="utf-8") as f:
            return json.load(f)

    # --- happy path: deliver -> running -> done (job deleted from inbox at delivery) ---
    root, backend, beacons, poller = fresh()
    job_id = seed(backend)
    poller.tick()
    st = status(backend, job_id)
    check(st["state"] == "delivered" and poller.active is not None, "claim -> delivered, slot taken")
    check(os.path.exists(os.path.join(root, "cncdisk", "demo_bracket.nc")), "nc delivered under its source name")
    check(job_id not in backend.list_inbox(), "delivered -> deleted from inbox (no retention)")

    beacons.feed(2)                          # jump to beacon 2 (slave reports the highest seen)
    poller.tick()
    st = status(backend, job_id)
    check(st["state"] == "running" and st["last_beacon"] == 2, "beacon -> running, last_beacon tracks")
    check(st["percent"] == 50.0 and st["op"] == "2D Contour2" and st["line"] == 40, "map lookup -> percent/op/line")
    check(st["eta_s"] == 20, "eta = total - cum")

    beacons.feed(4)                          # complete beacon
    poller.tick()
    st = status(backend, job_id)
    check(st["state"] == "done" and st["percent"] == 100.0, "complete beacon -> done @ 100%")
    check(poller.active is None, "done -> slot freed")

    # nothing left to claim (job was deleted from inbox at delivery)
    poller.tick()
    check(poller.active is None, "empty inbox -> nothing re-claimed")

    # --- deliver-only job (no map): delivered + deleted, no beacon watch, not re-claimed ---
    root, backend, beacons, poller = fresh()
    probe_id = "20260607T100000-probe_z"
    with open(os.path.join(backend.inbox, probe_id + ".nc"), "wb") as f:
        f.write(b"(probe Z)\nM30\n")              # NO .map.json -> deliver-only
    poller.tick()
    st = status(backend, probe_id)
    check(st["state"] == "delivered" and poller.active is None, "no map -> delivered, slot stays free (untracked)")
    check(os.path.exists(os.path.join(root, "cncdisk", "probe_z.nc")), "deliver-only name derived from jobId")
    check(probe_id not in backend.list_inbox(), "deliver-only deleted from inbox (controller retains it)")
    poller.tick()
    check(poller.active is None, "deliver-only job not re-claimed")

    # --- per-job marker: a job with a non-default marker is tracked against THAT marker ---
    root, backend, beacons, poller = fresh()
    job_id = seed(backend)
    with open(os.path.join(backend.inbox, job_id + ".map.json"), encoding="utf-8") as f:
        mp = json.load(f)
    mp["marker"] = 222
    with open(os.path.join(backend.inbox, job_id + ".map.json"), "w", encoding="utf-8") as f:
        json.dump(mp, f)
    poller.tick()                                 # claim -> beacons.reset(marker=222)
    beacons.feed(1)                               # SimBeaconSource now frames with marker 222
    poller.tick()
    check(status(backend, job_id)["last_beacon"] == 1, "beacon validated against the job's marker (222)")

    # --- FIFO: oldest jobId first ---
    root, backend, beacons, poller = fresh()
    seed(backend, "20260607T090000-second")
    seed(backend, "20260607T080000-first")    # earlier timestamp = should go first
    poller.tick()
    check(poller.active and poller.active["job_id"] == "20260607T080000-first", "FIFO: oldest jobId claimed first")

    # --- stall: no beacon after delivery -> stalled, slot freed ---
    root, backend, beacons, poller = fresh(stall=0.0)
    job_id = seed(backend)
    poller.tick()                             # deliver
    time.sleep(0.01)
    poller.tick()                             # watch: now > last_progress -> stall
    st = status(backend, job_id)
    check(st["state"] == "stalled" and poller.active is None, "no beacon -> stalled + slot freed")

    # --- delivery failure -> failed, queue not wedged ---
    root, backend, beacons, poller = fresh()
    job_id = seed(backend)

    class _Boom:
        def deliver(self, *a):
            raise OSError("simulated SMB failure")
    poller.transfer = _Boom()
    poller.tick()
    st = status(backend, job_id)
    check(st["state"] == "failed" and poller.active is None, "delivery error -> failed, slot not wedged")
    check(job_id not in backend.list_inbox(), "failed job removed from inbox (won't retry-loop)")

    # --- CNCDISK explorer: publish listing + safe delete via command channel ---
    from .cncdisk import CncDiskService
    root, backend, beacons, poller = fresh()
    cncdisk = os.path.join(root, "controller_disk")   # stands in for \\192.168.0.99\CNCDISK (separate from bucket)
    os.makedirs(cncdisk, exist_ok=True)
    for nm in ("keep.nc", "old.nc"):
        with open(os.path.join(cncdisk, nm), "wb") as f:
            f.write(b"(x)\nM30\n")                     # 8 bytes
    svc = CncDiskService(backend, cncdisk, refresh_s=0.0)

    svc.publish()
    with open(os.path.join(backend.cncdisk, "index.json"), encoding="utf-8") as f:
        idx = json.load(f)
    names = [x["name"] for x in idx["files"]]
    check(names == ["keep.nc", "old.nc"] and idx["files"][0]["size"] == 8, "index lists CNCDISK files + sizes")

    # web drops a delete command
    with open(os.path.join(backend.commands, "c1.json"), "w", encoding="utf-8") as f:
        json.dump({"op": "delete", "target": "old.nc"}, f)
    svc.tick()
    check(not os.path.exists(os.path.join(cncdisk, "old.nc")), "delete command removed the file from CNCDISK")
    check(os.path.exists(os.path.join(cncdisk, "keep.nc")), "delete only touched its target")
    check(not os.path.exists(os.path.join(backend.commands, "c1.json")), "processed command cleared")
    with open(os.path.join(backend.cncdisk, "index.json"), encoding="utf-8") as f:
        check([x["name"] for x in json.load(f)["files"]] == ["keep.nc"], "index refreshed after delete")

    # safety: path traversal + disallowed op are rejected, file system untouched, command cleared
    for bad in ({"op": "delete", "target": "../keep.nc"}, {"op": "run", "target": "keep.nc"}):
        with open(os.path.join(backend.commands, "bad.json"), "w", encoding="utf-8") as f:
            json.dump(bad, f)
        svc.tick()
        check(os.path.exists(os.path.join(cncdisk, "keep.nc")) and
              not os.path.exists(os.path.join(backend.commands, "bad.json")),
              f"rejected unsafe command {bad['op']}/{bad['target']} (file safe, command cleared)")

    print("\nself-test:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


# --------------------------------------------------------------------------- cli
def r2_check():
    """Live round-trip against a real R2 bucket: exercise all four Backend methods the way
    fairy depends on them (web would do the inbox PUTs). Needs boto3 + R2_* env vars. Cleans up."""
    import json
    cfg = Config.from_env(backend="r2")
    missing = [k for k, v in (("R2_ENDPOINT", cfg.r2_endpoint), ("R2_BUCKET", cfg.r2_bucket),
                              ("R2_ACCESS_KEY", cfg.r2_access_key), ("R2_SECRET_KEY", cfg.r2_secret_key)) if not v]
    if missing:
        print("Set these env vars first:", ", ".join(missing))
        return 2
    backend = make_backend(cfg)
    job_id = "__fairy_r2_check__"
    nc = b"(r2 check)\nM30\n"
    m = {"source": "r2_check.nc", "total_beacons": 1, "total_est_time_s": 1.0,
         "beacons": [{"n": 1, "orig_line": 2, "op": "end", "cum_time_s": 1.0, "percent": 100.0, "complete": True}]}

    ok = True

    def check(cond, label):
        nonlocal ok
        print(f"  [{'ok' if cond else 'FAIL'}] {label}")
        ok = ok and cond

    print(f"[r2-check] {cfg.r2_endpoint}  bucket={cfg.r2_bucket}")
    # seed an inbox job the way web/ would
    backend.s3.put_object(Bucket=backend.bucket, Key=f"inbox/{job_id}.nc", Body=nc)
    backend.s3.put_object(Bucket=backend.bucket, Key=f"inbox/{job_id}.map.json",
                          Body=json.dumps(m).encode("utf-8"))
    try:
        check(job_id in backend.list_inbox(), "list_inbox sees the seeded job")
        nc2, m2 = backend.get_job(job_id)
        check(nc2 == nc and m2.get("source") == "r2_check.nc", "get_job returns nc + map")
        backend.put_status(job_id, {"jobId": job_id, "state": "running", "percent": 50.0})
        raw = backend.s3.get_object(Bucket=backend.bucket, Key=f"status/{job_id}.json")["Body"].read()
        check(json.loads(raw)["state"] == "running", "put_status wrote status/")
        backend.delete_job(job_id)
        check(job_id not in backend.list_inbox(), "delete_job cleared inbox (no retention)")
    finally:
        for key in (f"inbox/{job_id}.nc", f"inbox/{job_id}.map.json",
                    f"status/{job_id}.json"):
            try:
                backend.s3.delete_object(Bucket=backend.bucket, Key=key)
            except Exception:
                pass
    print("\nr2-check:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv):
    if "--self-test" in argv:
        return self_test()
    if "--demo" in argv:
        return demo()
    if "--r2-check" in argv:
        return r2_check()

    ap = argparse.ArgumentParser(prog="fairy.bridge")
    ap.add_argument("cmd", nargs="?", default="run", choices=["run"])
    ap.add_argument("--backend", choices=["local", "r2"])
    ap.add_argument("--root", dest="local_root")
    ap.add_argument("--dest", dest="expert_dest")
    ap.add_argument("--port", dest="com_port")
    ap.add_argument("--baud", type=int)
    ap.add_argument("--slave", dest="slave_id", type=int)
    ap.add_argument("--stall", dest="stall_seconds", type=float)
    ap.add_argument("--poll", dest="poll_interval_s", type=float)
    args = ap.parse_args(argv)

    cfg = Config.from_env(
        backend=args.backend, local_root=args.local_root, expert_dest=args.expert_dest,
        com_port=args.com_port, baud=args.baud, slave_id=args.slave_id,
        stall_seconds=args.stall_seconds, poll_interval_s=args.poll_interval_s,
    )
    run_loop(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
