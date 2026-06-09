# ROADMAP

Forward-looking companion to [`README.md`](README.md) (which is "what is"). Last updated **2026-06-07**.
Goal: push G-code from anywhere, run it on the **DDCS Expert M350**, and read back how it went — without
exposing the machine. Foundations are proven; the work now is assembling them into the **`bridge-app/`**.

> Two controllers, never mixed — see [`AGENTS.md`](AGENTS.md). The bridge targets the **Expert** (studio).

---

## ✅ Done — foundations proven on the real machine (2026-06-06)
- **SMB R/W** to the Expert (`\\192.168.0.99\CNCDISK`/`SYSDISK`, guest=root) — push jobs, read state.
- **Modbus `MSETDATA`** push proven (COM6, 115200 8N1, slave 1; `reg = #(n+1)<<8|#n`, little-endian).
- **Beacon/checkpoint readback** proven (`CHECKPOINT_TEST.nc` → `28417/18/19`, wedge-free).
- **PC tooling:** `ddcs_lint.py` (syntax linter, validated vs ~70 macros), `modbus_slave.py`,
  `checkpoint_insert.py` (beacon instrumenter + map), `bridge_ui_mock.html`.
- **Design locked:** [`bridge-app/`](bridge-app/) (web ⇄ R2 ⇄ fairy), [`shared/PROTOCOL.md`](bridge-app/shared/PROTOCOL.md), [`TRANSPORT_DECISION.md`](TRANSPORT_DECISION.md).
- **Run-state/alarm var map**, syntax findings (`;` comments, `( )` can't nest), `M47`≠V4.1, all recorded in
  [`controllers/expert-m350/FINDINGS.md`](controllers/expert-m350/FINDINGS.md).

## 🎯 Now — build the bridge-app (order from `bridge-app/README.md`)
1. **`shared/PROTOCOL.md`** — locked (beacon frame fixed; map/R2/status free to evolve).
2. **`fairy/`** (headless, CNC-FAIRY) against a **LocalFolder** backend first: `poll inbox → deliver .nc to
   Expert (SMB) → run modbus_slave → write status`. Single active job (beacon has no job id). Reuse
   `modbus_slave.py`. End-to-end testable with **no cloud account**.
3. **Swap in the R2 backend** (Cloudflare) behind the same Backend seam.
4. **`web/`** (Cloudflare Pages + Worker) — submit + beacon-insert + queue + live tracker; reuse the UI mock.

## 🧰 Tooling backlog
- [ ] `ddcs_lint.py`: add a **G/M-code landmine scan** (`G02.4`/`G03.4`, `G10`, `G28`, `G41/G42`, canned
      cycles) so one pass does syntax + DDCS compatibility. Gate `web/` submissions on it.
- [ ] Linter rule: flag **live `MGETDATA`** without a confirmed-responding slave (it hard-wedges).
- [ ] [`CONFORMANCE_CORPUS.md`](controllers/expert-m350/CONFORMANCE_CORPUS.md): use the wired Expert as a
      parser oracle to build DDCS-Studio engine fixtures (cross-project).

## 🔬 Open experiments — need the machine + an E-stop (do NOT blind-test; each bad one = a reboot)
- [ ] **Remote start** without the panel: does `sysstart` re-Select+run a PC-named file? or a `#2037`
      virtual "Start" button? — this is the gate for hands-free delivery→run.
- [ ] **`error.nc` alarm routing:** confirm a macro in `error.nc` can `MSETDATA` an alarm code → PC.
- [ ] **Multi-channel watchdog:** status-pusher in analyze channel 2 reading channel 1's `#1630` safely.
- [ ] **Safe `MGETDATA`:** only after a bench Modbus master proves the slave answers the exact registers.

## ⚠️ Guardrails (hard-won — encoded in the linter)
- **Reading `#1630-#1636`** (analyze-channel status) from a job → **wedge → reboot.**
- **Blocking `MGETDATA`** (single channel, slave not answering) → **wedge → reboot.** Bridge is **push-only.**
- **Safety:** delivery is automatic; **running is operator-pressed.** No autonomous motion / jog without an
  independent hardware E-stop + watchdog ([`controllers/shared/ARCHITECTURE.md`](controllers/shared/ARCHITECTURE.md)).
- A printshop **guest WiFi isolates clients** → the bridge relays via the **cloud (R2)**, not a LAN link.

## 🌱 Later / maybe
- Pre-load multiple jobs on the controller (job tag in a 2nd register `#252`) — out of scope until needed.
- Live low-latency jog/control module (separate app, hard real-time, hardware-safety-gated).
