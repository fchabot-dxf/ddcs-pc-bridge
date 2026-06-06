# Controllers — V4.1 vs Expert (M350)

This project targets **two physically different DDCS controllers**. This folder keeps their
findings and assets separate so a fact proven on one is never silently assumed on the other.

## Disambiguation rule (for agents and humans)
0. **Confirm which physical device you're connected to** — run
   [`identify-controller.ps1`](identify-controller.ps1) (reads the firmware, prints `V4.1` or
   `EXPERT-M350`). Trust the verdict, not the IP. Two locations, two controllers — see
   [`ENVIRONMENTS.md`](ENVIRONMENTS.md).
1. Identify which controller a task is about *before* acting (bench V4.1 @ home, or studio Expert M350).
2. Use that controller's `FINDINGS.md` as the source of truth.
3. If a needed fact only exists for the *other* controller, treat it as `[HYPOTHESIS]` until
   re-confirmed on the one you're working with — **especially serial/Modbus and network direction.**
4. Log new results in the correct `FINDINGS.md` with a confidence tag.

## Comparison matrix (current best knowledge)

| Capability | DDCS V4.1 (bench, `10.0.0.50`) | DDCS Expert / M350 (target) |
|---|---|---|
| SMB file share over Ethernet | ✅ `[CONFIRMED]` R/W to `\\10.0.0.50\cncdisk` + `\sysdisk` (SMB1 + guest) | ✅ `[CONFIRMED 2026-06-06]` R/W to `\\192.168.0.99\CNCDISK`+`SYSDISK` (V4.1 recipe works; guest=root; SYSDISK=/mnt/nand1-1/, CNCDISK=/local/) |
| Network direction | controller **exposes** its disk; PC reads it `[CONFIRMED]` | exposes its disk, PC reads+writes it ✅ `[CONFIRMED 2026-06-06]`; also mounts PC-hosted `share` ("Net Disk") `[HYPOTHESIS]` |
| Default IP scheme | static `192.168.2.x` (we set `10.0.0.50`) | controller `192.168.0.99`, host `192.168.0.100`; manual-IP only |
| `uservar` store (slot = `#var−100`) | ✅ `[CONFIRMED]` on SYSDISK, 400×f64 (#100–#499) | ✅ `[CONFIRMED 2026-06-06]` on **CNCDISK** (`/local/uservar`), **450×f64 → #100–#549**; same `slot=#var−100`; read live over SMB |
| `uservar` as PC→program *inbound* channel | ❌ `[CONFIRMED]` program reads RAM; file writes ignored (readback-only) | `[TO TEST]` |
| Live inbound channel to a running program | ✅ via the **program file** — `M47` self-loop re-reads disk each cycle, PC overwrites it `[CONFIRMED]`; `uservar` vars do NOT | Modbus serial (`MGETDATA`) `[CONFIRMED via docs]` |
| Software dispatcher (1 bootstrap Start, then SMB-fed jobs) | ✅ `[CONFIRMED]` `M47` loop + overwrite file; no per-job trigger | `sysstart` loop = zero-touch `[likely]` |
| Remote job-swap: overwrite/delete+resend selected file, Start re-runs NEW code | ✅ `[CONFIRMED]` file re-read on Start (resolved by path) | `[TO TEST]` |
| Trigger a run (after a one-time manual file select) | dumb **Start pulse** → External Start input (~$6, NPN active-low) `[reload CONFIRMED; input TO TEST]` | `sysstart` boot hook = zero-hardware `[CONFIRMED via docs]` |
| `error.nc` = system-fault/alarm hook (NOT a syntax-error hook) | program errors don't fire it `[CONFIRMED]`; HW-alarm untested (no switches) | ✅ runs "when system abnormal working" `[CONFIRMED via docs]` |
| `#3000` alarm command (`#3000=1(MSG,…)`) | ❌ `[CONFIRMED]` unsupported → "macro variable assignment error" | ✅ `[CONFIRMED via docs]` |
| Boot-time auto-run hook | none confirmed; no `sysstart`; `advstart.nc` = Advanced-Start feature `[TO TEST]` | `sysstart.nc` boot-init `[CONFIRMED via docs]` |
| Home-all / startup-homing command | `G128 X1Y1Z1A1` or `M105`+`M106`+`M107`+`M108` `[CONFIRMED via manual]` | `M115` (firmware built-in) `[CONFIRMED]` |
| Detect a syntax error over Ethernet (uservar sentinel + checkpoints) | ✅ `[CONFIRMED]` clean *and* error cases | `[TO TEST]` |
| Run-state files `.file` / `.<f>.nc.env` / `.pos` on SYSDISK | ✅ `.file`=last file (useful); `.env` idx 148/149 do NOT track status `[REFUTED]` | `.<name>.nc.pos` (60 B) + `.break0/.break1` present `[CONFIRMED present 2026-06-06; semantics TO TEST]` |
| Serial = **Modbus RTU** (`MSETDATA`/`MGETDATA`) | ❌ `[CONFIRMED]` not in firmware (checked 2 builds) | ✅ `[CONFIRMED on machine]` **`#279`=Modbus RTU enable**, **`#267`**=Serial-2 baud (B115200), `#296`/`#297`=Serial-2 parity/stop → **115200 8N1**; `#284`=Network boot mode (fw 2025-06-19-00) |
| Serial port 1 = **M3K keyboard** | ✅ (listen test was silent — input port) | ✅ port 1 = M3K, port 2 = Modbus data |
| `#2037` virtual buttons (press panel keys from macro) | `[TO TEST]` | ✅ `[CONFIRMED]` (per ddcs-expert skill) |
| Passwords | Super Admin `888888` | Operator `666666` / Admin `777777` / Super Admin `888888` |

Legend: ✅ confirmed · ❌ confirmed-absent · `[TO TEST]` open · `[HYPOTHESIS]` unverified.

See [`v4.1/FINDINGS.md`](v4.1/FINDINGS.md) and [`expert-m350/FINDINGS.md`](expert-m350/FINDINGS.md)
for detail and provenance. Active V4.1 test backlog: [`v4.1/ETHERNET_TESTS.md`](v4.1/ETHERNET_TESTS.md).
