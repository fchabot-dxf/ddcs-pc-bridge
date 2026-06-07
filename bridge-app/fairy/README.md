# fairy/ — the headless bridge on CNC-FAIRY

App 2 of the bridge (see [`../ARCHITECTURE.md`](../ARCHITECTURE.md)). Outbound-only Python service on the
only PC cabled to the DDCS Expert. The loop: **poll the rendezvous store → write the `.nc` to the Expert
(SMB) → watch the Modbus slave for beacons → post progress back.** It never connects to `web/`; both meet
only at the bucket ([`../shared/PROTOCOL.md`](../shared/PROTOCOL.md)).

## Modules
| File | Role |
|---|---|
| `bridge.py` | entry point — wires modules, runs the loop (`run` / `--demo` / `--self-test`) |
| `config.py` | one place for COM port, dest, R2 creds (from env), timings |
| `poller.py` | the single-active-job state machine (PROTOCOL §4): claim → deliver → watch → done/stalled |
| `transfer.py` | SMB file copy to CNCDISK (one of the modules that touch the controller) |
| `slave.py` | beacon source: real `ModbusBeaconSource` (COM6) + hardware-free `SimBeaconSource` |
| `cncdisk.py` | CNCDISK file explorer: publish listing + safe `delete` command channel (PROTOCOL §7) |
| `tracker.py` | pure `(map, beacon) → status object` (PROTOCOL §2/§5) |
| `backend/` | the transport seam — `local_folder.py` (test) and `r2.py` (prod), same methods |

## Run it
No hardware or cloud needed for the first two:
```bash
cd bridge-app
python -m fairy.bridge --self-test   # offline logic checks (poller transitions, FIFO, stall, fail)
python -m fairy.bridge --demo        # full pipeline on a temp folder with simulated beacons
```
Live, against the real rig (needs `pip install -r fairy/requirements.txt`):
```bash
# local-folder backend, real Modbus slave + real SMB delivery:
python -m fairy.bridge run --backend local --root ./_bridge_data --dest \\192.168.0.99\CNCDISK --port COM6
# R2 backend (set R2_ENDPOINT/R2_BUCKET/R2_ACCESS_KEY/R2_SECRET_KEY first):
python -m fairy.bridge run --backend r2 --dest \\192.168.0.99\CNCDISK --port COM6
```

## Status
- [x] Backend seam + LocalFolder backend, Poller, Transfer, Tracker, Sim/Modbus slave, CNCDISK explorer — built, self-test + demo passing.
- [x] Two job types: tracked (Fusion, beacons) + deliver-only (probe, no map); no bucket retention (controller retains).
- [x] **SMB delivery proven live on the V4.1** (2026-06-07); **CNCDISK explorer (list + safe delete) proven live on the V4.1**.
- [x] `r2.py` — written (S3 API). **[TO TEST] live against a real bucket** (`--r2-check`, needs S3 token).
- [ ] Run live on the **Expert**: real Modbus beacons (COM6) end to end (only testable there).
- [ ] Register `bridge.py` as a Task Scheduler task (start at boot + on resume-from-sleep).
- [ ] (optional) `localui/` zero-lag local tracker.
