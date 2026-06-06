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

## Current status (2026-06-06)
- ✅ V4.1 file access over Ethernet (SMB) — full read/write.
- ✅ `error.nc` does **not** fire on syntax errors — pivoted to a completion-sentinel + decoding the
  controller's run-state `.env` (which appears to record the error line). Confirmation run pending.
- ⏭️ Next: confirm the `.env` error-line field, find the alarm-code variable, and stand up the
  Expert's Modbus channel.

## Safety
Bench V4.1 (no motors) is the dev rig. Autonomous control of the real Expert/Ultimate Bee requires an
independent hardware E-stop + watchdog — see [`controllers/shared/ARCHITECTURE.md`](controllers/shared/ARCHITECTURE.md).
