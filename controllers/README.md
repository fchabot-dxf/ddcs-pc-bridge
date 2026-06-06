# Controllers — V4.1 vs Expert (M350)

This project targets **two physically different DDCS controllers**. This folder keeps their
findings and assets separate so a fact proven on one is never silently assumed on the other.

## Disambiguation rule (for agents and humans)
1. Identify which controller a task is about *before* acting (bench V4.1, or studio Expert M350).
2. Use that controller's `FINDINGS.md` as the source of truth.
3. If a needed fact only exists for the *other* controller, treat it as `[HYPOTHESIS]` until
   re-confirmed on the one you're working with — **especially serial/Modbus and network direction.**
4. Log new results in the correct `FINDINGS.md` with a confidence tag.

## Comparison matrix (current best knowledge)

| Capability | DDCS V4.1 (bench, `10.0.0.50`) | DDCS Expert / M350 (target) |
|---|---|---|
| SMB file share over Ethernet | ✅ `[CONFIRMED]` R/W to `\\10.0.0.50\cncdisk` + `\sysdisk` (SMB1 + guest) | likely (Linux/Samba), `[TO TEST]` — test V4.1 recipe vs Expert IP |
| Network direction | controller **exposes** its disk; PC reads it `[CONFIRMED]` | both: exposes its disk **and** mounts PC-hosted `share` ("Net Disk") `[HYPOTHESIS]` |
| Default IP scheme | static `192.168.2.x` (we set `10.0.0.50`) | controller `192.168.0.99`, host `192.168.0.100`; manual-IP only |
| `uservar` store (400×f64, slot = `#var−100`, #100–#499) | ✅ `[CONFIRMED]` | likely same `[TO TEST]` |
| `error.nc` runs on a **syntax/parse error** | ❌ `[CONFIRMED]` does NOT fire | `[TO TEST]` |
| `error.nc` runs on a runtime **alarm** (`#3000`) | `[TO TEST]` (test armed) | `[TO TEST]` |
| Run-state files `.file` / `.<f>.nc.env` / `.pos` on SYSDISK | ✅ exist; `.env` int32 idx 149 ≈ error line `[HYPOTHESIS]` | `[TO TEST]` |
| Serial = **Modbus RTU** (`MSETDATA`/`MGETDATA`, `#279`/`#267`) | ❌ `[CONFIRMED]` not in firmware (checked 2 builds) | ✅ documented `[CONFIRMED via docs]`, params `[VERIFY ON MACHINE]` |
| Serial port 1 = **M3K keyboard** | ✅ (listen test was silent — input port) | ✅ port 1 = M3K, port 2 = Modbus data |
| `#2037` virtual buttons (press panel keys from macro) | `[TO TEST]` | ✅ `[CONFIRMED]` (per ddcs-expert skill) |
| Passwords | Super Admin `888888` | Operator `666666` / Admin `777777` / Super Admin `888888` |

Legend: ✅ confirmed · ❌ confirmed-absent · `[TO TEST]` open · `[HYPOTHESIS]` unverified.

See [`v4.1/FINDINGS.md`](v4.1/FINDINGS.md) and [`expert-m350/FINDINGS.md`](expert-m350/FINDINGS.md)
for detail and provenance.
