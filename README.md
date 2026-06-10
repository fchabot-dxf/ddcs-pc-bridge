# DDCS Homebrew Control API

A homebrew / reverse-engineering effort to build an **unofficial PC + AI control API** for DDCS CNC
controllers — push G-code, run it, and **read back whether it errored** (the primary goal). The DDCS
has no official PC API; this project synthesizes one from the interfaces the vendor built for humans
and accessories (SMB file share, serial keyboard/Modbus port, macro event-hooks, virtual buttons).

> **Most work in this repo is done by AI agents.** If you are an agent, start with
> **[`AGENTS.md`](AGENTS.md)**.

## Two controllers — don't mix them up
| | DDCS **V4.1** (bench) | DDCS **Expert / M350** (target) |
|---|---|---|
| Role | safe sandbox, no motors — on the LAN at `10.0.0.50` | real machine (Ultimate Bee 1010) |
| Serial | no Modbus (firmware) | **Modbus RTU** — the rich channel |

Findings are kept **separate per controller** because they genuinely differ. See the comparison
matrix in **[`controllers/README.md`](controllers/README.md)** and never cross-apply a fact without
checking it.

## Map
- **[`AGENTS.md`](AGENTS.md)** / [`CLAUDE.md`](CLAUDE.md) — agent entry point + the two-controller rule.
- [`archive/`](archive/) — historical/superseded originals (DESIGN, EXPERIMENTS, RS232 probe notes,
  packaged skill). Context only — current truth lives under `controllers/`.
- [`controllers/`](controllers/) — per-machine findings, build guides, and assets:
  - [`v4.1/FINDINGS.md`](controllers/v4.1/FINDINGS.md) · [`expert-m350/FINDINGS.md`](controllers/expert-m350/FINDINGS.md) · [`shared/ARCHITECTURE.md`](controllers/shared/ARCHITECTURE.md)
  - [`expert-m350/tools/`](controllers/expert-m350/tools/) — PC-side tools: `ddcs_lint.py`, `modbus_slave.py`, `orchestrator.py` (see its [README](controllers/expert-m350/tools/README.md))

## Current status (2026-06-06) — **the Expert is LIVE**
First in-person session with the real Expert M350 (studio). It went from documentation-only to a
fully-reachable, characterized target:
- ✅ **SMB read/write** to the Expert (`\\192.168.0.99\CNCDISK`+`SYSDISK`, guest=root) — V4.1 recipe ports as-is.
- ✅ **Modbus RTU proven live** — `MSETDATA` frames received by a PC slave (115200 8N1; little-endian
  byte pack). The Expert-only "rich channel" is real, not theoretical.
- ✅ **Checkpoint-sentinel readback proven on the machine** — the PC tracks how far a job ran (the core goal).
- ✅ **Run-state / alarm variable map** confirmed (`#1630` status, servo-alarm `#1000+`, etc.).
- ✅ **PC-side tooling** in [`controllers/expert-m350/tools/`](controllers/expert-m350/tools/) — `ddcs_lint.py`
  (syntax linter, validated vs ~70 macros), `modbus_slave.py`, `orchestrator.py`.
- 🔑 **Error readback, resolved:** syntax errors are yacc-generated and drawn to the screen only (not
  SMB-readable), so we **prevent** them with the linter and **detect** run failures via checkpoints;
  hardware/system faults route through `error.nc`.
- ⚠️ **Hazard learned live:** reading `#1630-#1636` (analyze-channel internals) from a job wedges the
  controller (needs a reboot). The linter flags it.
- 🏗️ The app this was building toward: **[`bridge-app/`](bridge-app/)** — push a job from anywhere → R2
  bucket → CNC-FAIRY (`fairy/`) → Expert over SMB, with live **beacon** progress (`MSETDATA` push). See its
  [`README`](bridge-app/README.md) + [`PROTOCOL`](bridge-app/shared/PROTOCOL.md). (`MGETDATA` inbound
  **hard-wedges** the controller — the bridge is **push-only**.)

## Safety
Bench V4.1 (no motors) is the dev rig. Autonomous control of the real Expert/Ultimate Bee requires an
independent hardware E-stop + watchdog — see [`controllers/shared/ARCHITECTURE.md`](controllers/shared/ARCHITECTURE.md).
