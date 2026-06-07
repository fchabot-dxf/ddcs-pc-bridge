# PROTOCOL — the contract between `web/` and `fairy/`

The two apps never talk directly; they rendezvous through the R2 bucket. This file is the seam both
sides must obey. Change it deliberately — a mismatch silently breaks the bridge.

---

## 1. Beacon frame (controller → Modbus slave) — CONFIRMED LIVE
The instrumented job sets two vars and pushes them at each safe retract:
```
#251 = 111        ; marker, set once near the top
#250 = <n>        ; beacon number, 1..255
MSETDATA[250,1,0,2,16,300]
```
`MSETDATA[250,1,0,2,16,300]` = write **2 bytes** from `#250` to **holding register 0** of slave id **1**,
function 16. Bytes pack little-endian within the register: `reg = (#251 << 8) | #250 = (111 << 8) | n`.

⇒ **The slave watches holding register 0. Each beacon arrives as `28416 + n`.**
- decode: `n = reg & 0xFF` (low byte)
- validate: `(reg >> 8) & 0xFF == 111` (the marker) — else it isn't a checkpoint frame, ignore it
- `n` runs `1 .. total_beacons`; the **last** `n` is the forced "complete" beacon (just before `M30`)

Proven on the machine 2026-06-06 (`CHECKPOINT_TEST.nc`): `n = 1/2/3` arrived as `28417 / 28418 / 28419`,
wedge-free. This frame is fixed — do not change `#250/#251/111/[...,0,2,16,300]` without re-proving live.

> ⚠️ **The frame carries NO job id** — only the beacon number. See §4 (single active job).

---

## 2. The map (per-job, produced by the instrumenter)
`web/` (or `checkpoint_insert.py`) emits, alongside the instrumented `.nc`, a JSON map so a bare beacon
number becomes percent / op / line / ETA:
```json
{
  "source": "bracket_v3.nc",
  "var": 250, "marker_var": 251, "marker": 111,
  "msetdata": "MSETDATA[250,1,0,2,16,300]",
  "total_est_time_s": 512.0,
  "total_beacons": 7,
  "beacons": [
    { "n": 1, "orig_line": 14, "op": "2D Contour1", "cum_time_s": 31.2, "percent": 6.1, "complete": false },
    { "n": 7, "orig_line": 803, "op": "Finish",     "cum_time_s": 512.0, "percent": 100.0, "complete": true }
  ]
}
```
- `percent` is **time-weighted** (cum_time / total) — not line-ratio — so the bar tracks wall-clock.
- Lookup: on beacon `n`, find `beacons[n-1]` → `percent`, `op`, `orig_line`. ETA = `total_est_time_s − cum_time_s`.
- Schema authority: [`../../controllers/expert-m350/tools/checkpoint_insert.py`](../../controllers/expert-m350/tools/checkpoint_insert.py).

---

## 3. R2 bucket layout
| Key | Writer | Reader | Meaning |
|---|---|---|---|
| `inbox/<jobId>.nc` | web | fairy | job waiting to be delivered (the **queue**) |
| `inbox/<jobId>.map.json` | web | fairy | its map — **only for TRACKED jobs** (see job types) |
| `status/<jobId>.json` | fairy | web | live progress (see §5) |
| `gateway/heartbeat.json` | fairy | web | gateway liveness + descriptor (`machine_id`, `name`, `last_seen`, `active_job`) — so the cloud console knows if the gateway is awake (CONFIGS §6) |

- **`jobId`** is **lexicographically sortable** = creation order, e.g. `20260606T143207-bracket_v3`.
  The queue is "`LIST inbox/` sorted ascending" → strict FIFO.
- `web` PUTs to `inbox/`; `fairy` LISTs `inbox/` and takes the **oldest**.
- **Two job types, keyed off the presence of a map (the "beacons" toggle in web):**
  - **TRACKED** — has a `.map.json` (e.g. a Fusion cut, instrumented). fairy watches beacons → progress.
  - **DELIVER-ONLY** — no map (e.g. a DDCS-Studio probe / utility `.nc`). fairy delivers it and marks it
    `delivered` (terminal); no beacon watch. These never need beacons.
- **No bucket retention (decided 2026-06-07).** There is no `archive/`/`kept/`. fairy **deletes
  `inbox/<jobId>.*` the instant delivery succeeds** — for *both* job types. Rationale: the file now lives on
  the **controller's CNCDISK**, which is where a same-session re-run comes from anyway (re-select + Start on
  the panel); days later the operator regenerates. So the controller is the de-facto retention; a bucket copy
  buys nothing. Deleting on delivery is also the idempotency mechanism (a delivered job is gone from the
  queue) **and** an operational-safety win: a crashed/restarted fairy can't re-deliver a job mid-cut.
  Only `status/<jobId>.json` (metadata: percent/op/line — no G-code) persists, as the web tracker's mirror.

---

## 4. Single active job (forced by §1)
Because the beacon frame has no job id, **only one job may be "active" (running + tracked) at a time.**
The bridge serializes:
```
fairy loop:
  if no active job and inbox not empty:
     jobId = oldest in inbox
     read inbox/<jobId>.nc (+ .map.json if present; hold the map in RAM)
     copy the .nc  →  Expert CNCDISK     (deliver)
     DELETE inbox/<jobId>.*              (delivered → controller has it; see §3)
     if no map (DELIVER-ONLY): status = "delivered" (terminal); done — slot stays free
     else (TRACKED): reset the slave to this job's marker; mark active; status = "delivered"
  while active:
     read holding[0]; if a NEW valid beacon n arrives → status = "running", update from the in-RAM map
     if n == total_beacons (complete) → status = "done"; active = none
     if no beacon for STALL_SECONDS after first → status = "stalled" (operator hasn't pressed Start, or it errored)
```
- Delivering one-at-a-time keeps beacon attribution unambiguous and matches the operator running jobs in
  order. The cloud `inbox/` still holds the whole queue; it just drains as each job is delivered.
- Tracking after delivery runs entirely off the **in-RAM map + the live beacon stream** — no bucket file
  is read during a run. (RAM-only is operationally safe: the map has no control authority; losing it to a
  fairy crash costs only the progress bar for that one in-flight job, never the cut.)
- **Future** (not v1): to pre-load several jobs on the controller, encode a job tag in a second register
  (e.g. set `#252` and push 4 bytes). Out of scope until needed.

---

## 5. Status object (`status/<jobId>.json`, fairy → web)
```json
{
  "jobId": "20260606T143207-bracket_v3",
  "name": "bracket_v3.nc",
  "state": "running",
  "last_beacon": 4,
  "total_beacons": 7,
  "percent": 61.0,
  "op": "Drill 6mm",
  "line": 3000,
  "eta_s": 198,
  "updated_at": "2026-06-06T14:32:07Z",
  "events": [ "delivered → Expert", "running" ]
}
```
**States:** `queued` (in inbox, web's view) → `delivered` (on Expert disk) → `running` (beacons arriving)
→ `done` (complete beacon) · or `stalled` (no beacons after delivery+grace) · `failed` (delivery/IO error).
For a **deliver-only** job (no map; §3), `delivered` is the **terminal** state — there's no `running`/`done`.

`web` polls `status/<jobId>.json` for the tracker; `percent`/`op`/`line`/`eta_s` come straight from the
map lookup on `last_beacon`. The truly-live view is on fairy (direct from the slave); this is the mirror.

---

## 6. What is fixed vs free
- **Fixed (don't change without re-proving on the machine):** the beacon frame (§1).
- **Free (either app can evolve as long as both agree here):** the map fields beyond `n/percent`, the R2
  key names, the status fields. Bump a `"protocol": 1` field on objects if we ever break compatibility.

---

## 7. CNCDISK file explorer + command channel
A view of the controller's CNCDISK (and the ability to tidy it) from the web app. fairy is the only PC
cabled to the controller, so it publishes the listing and executes the actions.

| Key | Writer | Reader | Meaning |
|---|---|---|---|
| `cncdisk/index.json` | fairy | web | listing of the controller's CNCDISK (refreshed on a cadence) |
| `commands/<cmdId>.json` | web | fairy | a file-management command for fairy to execute (then delete) |

**`cncdisk/index.json`:**
```json
{ "path": "\\\\192.168.0.99\\CNCDISK", "updated_at": "2026-06-07T13:00:00Z",
  "files": [ { "name": "bracket_v3.nc", "size": 18422, "mtime": 1781000000 } ] }
```
(On an unreachable controller it carries `"files": []` + an `"error"` string instead of failing.)

**`commands/<cmdId>.json`** — `{ "op": "delete", "target": "old.nc" }`. fairy LISTs `commands/`, runs each,
then deletes it (processed once, good or bad — a poisoned command can't wedge the loop). After any change
it republishes `cncdisk/index.json`, so the file vanishing from the listing is the web app's confirmation.

**Safety (enforced on fairy — this is the only web→controller action):**
- **Op allowlist = `{delete}` only.** Never an op that runs/starts G-code. Reject anything else.
- **`target` must be a bare filename that already exists** on CNCDISK — no path separators, no traversal.
- fairy stays outbound-only (it *polls* `commands/`); the **web Worker's token gates who can write**
  `commands/`. fairy logs every command it executes.
- Proven live on the V4.1 (2026-06-07): list + traversal-refused + safe delete.
