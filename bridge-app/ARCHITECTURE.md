# bridge-app — Architecture

Extensive, module-by-module design for the DDCS Expert job bridge. The system is **two independent
("parallel") apps** that communicate only through a cloud bucket. This document is the map: every module,
**where it runs**, and **what it does**. Code should follow this structure.

- The contract between the apps: [`shared/PROTOCOL.md`](shared/PROTOCOL.md)
- Why cloud-poll (not an exposed endpoint): [`../TRANSPORT_DECISION.md`](../TRANSPORT_DECISION.md)
- The confirmed facts this is built on: [`../controllers/expert-m350/FINDINGS.md`](../controllers/expert-m350/FINDINGS.md)

---

## 1. System overview

```
        ╔═══════════════ APP 1: web/  (Cloudflare — runs "anywhere") ═══════════════╗
        ║  UI ░ Instrument (beacons) ░ Queue client ░ Tracker        │ Worker (auth+R2) ║
        ╚════════════════════════════════╤═════════════════════════════════╤══════════╝
                                          │ PUT job+map / GET status        │
                                          ▼                                 ▼
              ┌────────────────────── R2 bucket (the rendezvous) ──────────────────────┐
              │  inbox/<jobId>.nc(+map)   status/<jobId>.json   (deleted on delivery)   │
              └────────────────────────────────┬─────────────────────────▲─────────────┘
                                          GET job / LIST inbox        PUT status
                                               ▼                          │
        ╔═══════════════ APP 2: fairy/  (CNC-FAIRY — the only wired PC) ═══════════════╗
        ║  Poller ─▶ Transfer (SMB) ─▶ Expert    Slave (COM6) ─▶ Tracker ─▶ Backend     ║
        ╚════════════════════════════════════════════╤════════════════════════════════╝
                                                      │ cable (192.168.0.x, isolated)
                                                      ▼
                                                 [ DDCS Expert ]
```

**The two apps never connect to each other.** App 1 writes jobs to R2 and reads status from R2; App 2
reads jobs from R2 and writes status to R2. This decoupling is what delivers the queue, offline-tolerance
("submit while CNC-FAIRY sleeps, it auto-completes on wake"), and the un-exposed machine.

---

## 2. Design principles
1. **Two parallel apps, one bucket.** No direct app-to-app connection; R2 holds all shared state.
2. **Modular.** Each app is a set of small single-purpose modules with explicit inputs/outputs. Swappable
   parts (the transport backend, the cloud provider) sit behind interfaces.
3. **The machine is never internet-reachable.** `fairy/` makes only *outbound* calls. No inbound listener.
4. **Deliver, don't run.** The app lands files on the controller; the **operator presses Cycle Start**.
   No remote start, no jog, no live motion — those are out of scope (see §10 Safety).
5. **The beacon frame is sacred.** It is proven on real hardware; only the map/queue/status formats evolve.
6. **Testable without hardware or cloud.** A `LocalFolder` backend lets the whole pipeline run on one PC.

---

## 3. APP 1 — `web/`  (the operator-facing web app)

**Location:** Cloudflare — **Pages** (static UI) + a **Worker** (API). Opened in a browser from the ASUS,
a phone, anywhere. **Never runs on CNC-FAIRY.**
**Function:** everything the operator touches — **send code, insert beacons, manage the queue, watch the
tracker.** Holds no machine access; its only outside contact is the R2 bucket (via its Worker).
**Tech:** HTML/CSS/JS (no framework required); Cloudflare Worker (JS/TS); R2 binding.

### Modules
| Module | Path | Runs in | Function |
|---|---|---|---|
| **UI** | `web/ui/` | browser (Pages) | The dashboard: submit view, queue view, tracker view. Design = [`bridge_ui_mock.html`](../controllers/expert-m350/tools/bridge_ui_mock.html). |
| **Instrument** | `web/instrument/` | browser (client-side) | Parse the `.nc`, insert ≤255 time-paced beacons on Z-up retracts, emit instrumented `.nc` + map. JS port of `checkpoint_insert.py` (its self-test is the spec). |
| **Queue client** | `web/ui/queue.js` | browser | Upload job+map to `inbox/`, list the operator's jobs, drive the submit form — all via the Worker. |
| **Tracker** | `web/ui/tracker.js` | browser | Poll `status/<jobId>.json`, render `% · op · line · ETA`, advance the queue as jobs finish. |
| **Worker / API** | `web/worker/` | Cloudflare edge | The authenticated **API** to R2 so the **browser never holds R2 keys** (not to be confused with the *gateway* = fairy). Endpoints: `POST /jobs` (put inbox), `GET /jobs` (list), `GET /status/:id`. Enforces the access token. |

### Module detail
- **UI** — three tabs (Submit · Queue · Tracker). Static, served by Pages. Talks only to the Worker.
- **Instrument** — the one piece of real logic in the browser. Input: a raw `.nc` (File). Output: `{nc, map}`
  (see PROTOCOL §2). Must match `checkpoint_insert.py` byte-for-byte on the frame. Sub-parts:
  `gcode-parse.js` (modal G/X/Y/Z/F, Z-up detection, time estimate), `instrument.js` (pacing + emit).
- **Queue client** — turns "drop a file" into: instrument → `POST /jobs` (multipart: nc + map) → show "queued".
- **Tracker** — pure view over `status/`. The authoritative live view is on `fairy/` (zero lag); this mirror
  is a few seconds behind by design.
- **Worker** — the *only* code with the R2 credentials. Verifies the token, mediates every R2 op. Keeps the
  bucket private and the browser keyless.

**Deploys to:** Cloudflare Pages (UI) + `wrangler deploy` (Worker). Git-based deploy from this folder.

---

## 4. APP 2 — `fairy/`  (the headless bridge on CNC-FAIRY)

**Location:** **CNC-FAIRY** — the Panasonic Toughbook, the *only* PC physically cabled to the Expert
(`192.168.0.100 ↔ .99`). Runs as a background service. **No UI** (except an optional local mirror, §4.7).
**Function:** the hardware bridge — **poll R2 → write the `.nc` to the Expert (SMB) → run the Modbus slave →
post progress to R2.** Outbound-only; never internet-reachable.
**Tech:** Python 3; `pymodbus==3.6.9` (pinned — 3.13 broke the datastore); SMB via a mapped drive; an R2
(S3) client. Auto-starts on boot **and** on resume-from-sleep (Task Scheduler).

### Modules
| Module | Path | Function |
|---|---|---|
| **Entry / service** | `fairy/bridge.py` | Wires the modules together; runs the loop; handles startup/shutdown/logging. |
| **Config** | `fairy/config.py` | COM port, Expert drive path/UNC, R2 creds, poll interval, stall timeout. One place. |
| **Poller** | `fairy/poller.py` | The state machine: LIST `inbox/`, pick oldest, enforce **one active job** (PROTOCOL §4), drive transitions delivered→running→done/stalled. |
| **Transfer** | `fairy/transfer.py` | Copy the `.nc` onto the Expert's CNCDISK over SMB (`\\192.168.0.99\CNCDISK`, confirmed R/W). One of two modules that touch the controller. |
| **Slave** | `fairy/slave.py` | Run the Modbus RTU slave on COM6; watch holding reg 0; decode `28416+n → beacon n` (PROTOCOL §1). Wraps/extends [`modbus_slave.py`](../controllers/expert-m350/tools/modbus_slave.py). |
| **CNCDISK explorer** | `fairy/cncdisk.py` | Publish a listing of the controller's CNCDISK (`cncdisk/index.json`) and execute web-issued **delete** commands over SMB, with an op-allowlist + target validation (PROTOCOL §7). Touches the controller. |
| **Tracker** | `fairy/tracker.py` | Map `last_beacon` → `% / op / line / ETA` via the job map; build the status object (PROTOCOL §5). |
| **Identity** | `fairy/identity.py` | Machine identity on the controller's disk: provision `.bridge-machine.json`; verify-before-deliver (CONFIGS §7). Touches the controller. |
| **Ops** | `fairy/ops.py` | The **API-first operations surface** (`submit_job`, `list_queue`, `get_status`, `list_files`, `read_file`, `delete_file`, `descriptor`). One definition reused by the local server + future MCP/embeds. |
| **Local server** | `fairy/server.py` | Stdlib HTTP server exposing Ops as JSON + serving the console at `/` — how the gateway serves the console offline/on the LAN (CONFIGS §3). |
| **Backend** | `fairy/backend/` | The transport seam (interface). `local_folder.py` (test), `r2.py` (prod). `list_inbox`/`put_job`/`get_job`/`put_status`/`get_status`/`list_statuses`/`delete_job`/`put_cncdisk_index`/`list_commands`/`clear_command`/`put_heartbeat`. |
| **Local UI** *(optional)* | `fairy/localui/` | *(superseded by `server.py` serving the console — kept as a label for the zero-lag local view)* |

### Module detail
- **Poller** — the heart. Holds the single-active-job rule (because beacons carry no job id, PROTOCOL §4).
  Sequence per job: claim oldest from `inbox/` → `Transfer` → **`delete_job` (no retention, PROTOCOL §3)** →
  status `delivered` → watch `Slave` for the job's beacons (translated via the in-RAM map) → on `complete`
  beacon free the slot; on stall timeout, mark `stalled`.
- **Transfer** — input: a local `.nc` path; action: SMB file copy to the mapped Expert drive; output: success
  or IO error → status `failed`. Isolated so the risky/hardware bit is one auditable module.
- **Slave** — long-running; exposes "latest valid beacon n + timestamp" to the Poller/Tracker. Validates the
  `111` marker before accepting a frame. Never issues reads to the controller (no MGETDATA — would wedge it).
- **Tracker** — pure function: `(map, last_beacon) → status object`. No side effects beyond handing the object
  to `Backend.put_status`.
- **Backend** — the swap point between **local testing** and **R2**. Same 4 methods; the Poller/Tracker are
  backend-agnostic. This is how we run the whole thing on one machine before any cloud account exists.

**Deploys to:** CNC-FAIRY. Install Python + `requirements.txt`; register `bridge.py` as a Task Scheduler
task (triggers: at startup, on workstation unlock, on system resume).

---

## 5. `shared/`  (the contract)
**Location:** repo only (documentation; the two apps are different languages, so "shared" = the spec, not
shared code). **Function:** define the seam so `web/` and `fairy/` agree without ever talking.
- [`shared/PROTOCOL.md`](shared/PROTOCOL.md) — beacon frame (§1, fixed/proven), map schema (§2), R2 layout
  (§3), single-active-job rule (§4), status object (§5).

---

## 6. End-to-end data flow

**Outbound (submit a job):**
1. Operator drops `bracket_v3.nc` in the **web UI**.
2. **Instrument** (browser) inserts beacons → `{nc, map}`.
3. **Queue client** → **Worker** `POST /jobs` → R2 `inbox/<jobId>.nc` + `inbox/<jobId>.map.json`.
4. **Poller** (fairy) LISTs `inbox/`, takes the oldest `jobId`.
5. **Transfer** copies the `.nc` onto the Expert's CNCDISK over SMB. Status → `delivered`.
6. Operator selects it on the panel and **presses Start** (the only manual step).

**Inbound (watch progress):**
7. The job runs; at each safe retract it `MSETDATA`s a beacon → **Slave** (COM6) reads `28416+n`.
8. **Tracker** maps `n` → `% / op / line / ETA` → status object.
9. **Backend** PUTs `status/<jobId>.json` to R2.
10. Web **Tracker** polls `status/` → the operator sees the bar move (and live, zero-lag, on the optional
    `fairy/localui` right at the machine).

---

## 7. Folder / module map
```
bridge-app/
  ARCHITECTURE.md            ← this file
  README.md                  ← overview
  shared/
    PROTOCOL.md              ← the contract (web ⇄ fairy)
  web/                       ── APP 1: the Console (Cloudflare or gateway-served; runs anywhere) ──
    ui/        index.html · styles.css · app.js (shell+view registry) · client.js (transport seam) ·
               util.js · views/{submit,queue,files,admin}.js   [built; offline end-to-end verified]
    instrument/ instrument.js · gcode-parse.js          (beacon insertion, browser — Phase 4)
    worker/    api.js · auth.js                          (authed R2 API — Phase 3)
    wrangler.toml
  fairy/                     ── APP 2 (CNC-FAIRY; the wired PC) ──
    bridge.py                  entry / service loop
    config.py
    poller.py                  queue drainer + single-active-job state machine
    transfer.py                SMB write to the Expert
    slave.py                   Modbus slave + beacon decode
    cncdisk.py                 CNCDISK listing + safe delete-command channel (PROTOCOL §7)
    tracker.py                 beacon → status (via map)
    identity.py                machine identity (provision + verify-before-deliver)
    ops.py                     API-first operations surface (server + future MCP/embeds)
    server.py                  local HTTP server (serve console + ops API) — offline/local
    backend/   __init__.py (interface) · local_folder.py · r2.py
    localui/   server.py · index.html   (optional, zero-lag local view)
    requirements.txt
```

---

## 8. Physical setup — two PCs and a controller

The bridge spans **three physical nodes**, all at the studio. They have different roles, networks, and
access — this is "how the 2 PCs + the controller are actually used."

```
  [ ASUS · Fred-ASUS-TUF ]        [ CNC-FAIRY · Toughbook ]        [ DDCS Expert · M350 ]
  design + operator console       the bridge gateway              the CNC controller
  runs: web app (in a browser)    runs: fairy/ bridge (Python)    runs: firmware
  Wi-Fi 192.168.1.108             Wi-Fi 192.168.1.216 (internet)  Eth 192.168.0.99 (isolated)
        |                         Eth  192.168.0.100 ── SMB files ────▶ |
        |                         COM6 (SABRENT) ───── Modbus beacons ──▶ |
        |  guest Wi-Fi — clients ISOLATED, no direct PC↔PC link
        └──────────────┐      ┌────────────── (internet)
                       ▼      ▼
                [ R2 bucket — the ONLY place the two PCs meet ]
```

### The three nodes
| Node | hostname | role | runs | networks | touches the controller |
|---|---|---|---|---|---|
| **ASUS** | `Fred-ASUS-TUF` | design + operator console (CAM/Fusion lives here) | the **web app**, in a browser | studio Wi-Fi `192.168.1.108` | **no** |
| **CNC-FAIRY** | Panasonic Toughbook | the **bridge gateway** (fixed, tethered) | the **`fairy/`** bridge (Python service) | Wi-Fi `192.168.1.216` (internet) **+** private cable `192.168.0.100` | **yes** |
| **Expert** | DDCSE-5T (M350) | the CNC controller on the Ultimate Bee 1010 | firmware | private cable `192.168.0.99` only | — |

### The links between them
- **ASUS ↔ CNC-FAIRY — no direct link.** Both sit on the studio guest Wi-Fi (`LImprimerie-Invite`), but it
  **isolates clients** (confirmed 2026-06-06: ping + SMB fail both ways). So the two PCs **only ever meet at
  the R2 bucket**, over the internet. This is exactly why the transport is cloud-poll.
- **CNC-FAIRY ↔ Expert — two cables, both from CNC-FAIRY:**
  1. **Ethernet** `192.168.0.100 ↔ .99` → **SMB file delivery** (`transfer` writes the `.nc` to CNCDISK).
  2. **SABRENT FTDI serial**, CNC-FAIRY **COM6** ↔ Expert **port 2** → **Modbus beacons** (`slave` reads
     them). Requires `#279` Modbus enable + reboot.
- **ASUS ↔ Expert — never.** No path by design; the design laptop is never on the controller's network.

### Why it's split this way
- **CNC-FAIRY is the only machine that can be cabled to the controller** (Ethernet for files + serial for
  beacons), so it stays put next to the machine and runs the headless bridge. It is *not* a workstation.
- **The ASUS is the comfortable, mobile console** — CAM runs there, and you submit + watch from there. It is
  *not* cabled to the machine, and the guest Wi-Fi won't let it reach CNC-FAIRY directly — so the **cloud
  bridges the two PCs.**
- In one line: **one PC at the machine (gateway), one PC at the desk (console), a bucket in between because
  the local network keeps them apart.**

> Not part of this setup: **renderranchy**, the *home* V4.1 bench PC — different site, different controller.
> See [`../controllers/ENVIRONMENTS.md`](../controllers/ENVIRONMENTS.md).

---

## 9. Where every module runs (location summary)
| Module | Machine / platform | Language | Touches the machine? |
|---|---|---|---|
| web/ui, web/instrument, web/ui/* | browser (Cloudflare Pages) | JS | no |
| web/worker | Cloudflare edge | JS/TS | no |
| R2 bucket | Cloudflare | — | no |
| fairy/poller, /tracker, /backend, /config | CNC-FAIRY | Python | no (orchestration) |
| **fairy/transfer** | CNC-FAIRY | Python | **yes — SMB write to CNCDISK** |
| **fairy/slave** | CNC-FAIRY | Python | **yes — serial COM6** |
| **fairy/cncdisk** | CNC-FAIRY | Python | **yes — SMB list + delete on CNCDISK** |
| fairy/localui | CNC-FAIRY (localhost) | Python + JS | no |

Only **three** modules touch the controller — `transfer` (file write), `slave` (serial read), and
`cncdisk` (SMB list + delete). All isolated so the hardware surface is small and auditable. Only `cncdisk`'s
delete is web-triggered, and it's gated by an op-allowlist + target validation (PROTOCOL §7).

---

## 10. Safety boundaries
- **Deliver ≠ run.** No module presses Start. Files land on the controller; a human runs them.
- **No inbound to the controller.** `slave` only *reads* what the controller pushes; it never issues
  `MGETDATA` (that hard-wedges the Expert → reboot). The bridge cannot command motion.
- **No jog / live control.** Explicitly out of scope; a future *separate, local, low-latency, E-stopped*
  module — never the cloud path (see `../controllers/shared/ARCHITECTURE.md`).
- **Controller isolated.** `transfer` is the only path to it, over the private cable; its open `guest=root`
  SMB never reaches a shared/public network.
- **Machine un-exposed.** `fairy/` is outbound-only; nothing on CNC-FAIRY listens to the internet.

---

## 11. Build order & status
1. [x] `shared/PROTOCOL.md` — the seam.
2. [x] Beacon instrumenter reference (`checkpoint_insert.py`, Python) — built, self-test passing.
3. [x] UI mockup (`bridge_ui_mock.html`).
4. [x] `fairy/` against the **LocalFolder** backend → relay → tracker on one PC (`--self-test` + `--demo` pass).
5. [~] `fairy/backend/r2.py` — written (S3 API); **[TO TEST]** live against a real bucket.
6. [ ] `web/` — Pages UI + Instrument (JS) + Worker, on R2.
7. [ ] Deploy: Worker/Pages to Cloudflare; `bridge.py` as a CNC-FAIRY startup/resume task.
8. [ ] (optional) `fairy/localui` zero-lag local tracker.
```
```
