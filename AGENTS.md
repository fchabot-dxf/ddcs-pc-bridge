# AGENTS.md — read this first

This repo is a **homebrew / reverse-engineering effort to build an unofficial PC + AI control
API for DDCS CNC controllers**. Most work here is done *by* AI agents. This file is your entry point.

## ⛔ The one rule that matters: there are TWO different controllers

| | Bench unit (home) | Real target (studio) |
|---|---|---|
| Model | **DDCS V4.1** | **DDCS Expert (M350)** |
| Role | safe sandbox — no motors, no switches | production machine (Ultimate Bee 1010) |
| On the LAN | `10.0.0.50` (live, reachable now) | not on this network |

**They do NOT behave the same.** A fact confirmed on the V4.1 is *not* automatically true on the
Expert, and vice-versa (the clearest example: **Modbus serial exists on the Expert but is absent
from V4.1 firmware**). Before you rely on any finding, check which controller it was confirmed on.

➡️ **Never cross-apply a finding without checking [`controllers/README.md`](controllers/README.md)**
(the comparison matrix). When you confirm something new, record it under the *correct* controller's
`FINDINGS.md` with a confidence tag.

## Confidence tags (use these everywhere)
- `[CONFIRMED]` — verified on the named controller (bench test or firmware analysis).
- `[TO TEST]` — a concrete, bench-testable open question.
- `[HYPOTHESIS]` — best guess, unverified. Flag for human validation.

## Where things live
```
/AGENTS.md            ← you are here
/CLAUDE.md            ← pointer to this file (auto-loaded by Claude Code)
/README.md            ← human-facing project overview
/archive/             ← historical/superseded originals (DESIGN.md, EXPERIMENTS.md, RS232 probe
                        notes, packaged skill) — context only, NOT current (see archive/README.md)

/controllers/
  README.md           ← ⭐ V4.1-vs-Expert comparison matrix + disambiguation rule
  v4.1/
    FINDINGS.md       ← what is CONFIRMED on the bench V4.1
    DDCS_PC_BUILD_setup.md   ← get a PC talking to the V4.1 (SMB + serial)
    assets/           ← firmware backup, system snapshot, uservar snapshots, setting, error.nc.bak
  expert-m350/
    FINDINGS.md       ← what is known about the Expert (mostly from docs, [VERIFY ON MACHINE])
    DDCS_Expert_BUILD_setup.md  ← Expert setup (Modbus + Net Disk)
    assets/           ← Russian M350 Modbus docs, scope captures
  shared/
    ARCHITECTURE.md   ← controller-agnostic concepts (the homebrew API, dispatcher, safety)
```

## External reference (NOT part of this repo)
- `../DDCS-Expert-skill/` and the installed **`ddcs-expert`** Claude skill — deep DDCS macro/G-code
  knowledge (V1.22 verified). Consult it for G-code quirks, variable maps, virtual buttons (`#2037`).
  It is *reference only*; do not edit it as part of this repo.

## The goal, in one line
Push G-code from a PC, run it, and **read back whether it errored (and ideally which error/line)** —
eventually closing an AI-in-the-loop. Live motor position is explicitly *not* a goal.

## Safety (non-negotiable on the real machine)
Bench V4.1 (no motors) is the safe dev rig. Any autonomous control of the **Expert/Ultimate Bee**
requires an independent hardware E-stop + watchdog. See `controllers/shared/ARCHITECTURE.md`.
