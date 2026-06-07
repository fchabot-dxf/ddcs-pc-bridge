# Expert (M350) PC-side tools

PC-side bridge tooling for the **DDCS Expert M350** (studio). All proven on the real machine 2026-06-06.
See [`../FINDINGS.md`](../FINDINGS.md) for the why behind each.

## Quick reference (studio rig)
| | value |
|---|---|
| Controller IP | `192.168.0.99` (SMB shares `CNCDISK`=/local/, `SYSDISK`=/mnt/nand1-1/, guest=root) |
| Serial (Modbus) | SABRENT FTDI = **COM6**, **115200 8N1**, controller is **master**, slave id **1**, data on **port 2** |
| Python deps | **`pip install "pymodbus==3.6.9" pyserial openpyxl`** — pymodbus 3.13 broke the classic datastore, pin 3.6.x |

---

## `ddcs_lint.py` — syntax linter (run this BEFORE pushing any macro/job)
The controller's `syntax error:Ln` is yacc-generated and only drawn to the screen — it is NOT readable over
SMB. So catch errors on the PC first. Validated against ~70 production + factory macros (clean except one
real bug it caught). Pure offline, no machine needed.
```
python ddcs_lint.py mymacro.nc            # lint one
python ddcs_lint.py *.nc                   # lint many
python ddcs_lint.py --self-test            # built-in checks
```
Catches (ERROR = breaks/wedges, WARN = quirk): nested `()` comments (`E-NESTPAREN`), unbalanced `[]`
(`E-BRACKET`), `GOTO 1` spacing (`E-GOTOSPACE`), wrong `MSETDATA/MGETDATA` argc (`E-MARGS`), **reading
`#1630-#1636`** the analyzer-wedge (`E-CH1630`); warns on FANUC ops, `G10`, bare-const `G53`,
`#2070`→persistent, priming. Exit code = number of ERRORs.
DDCS comments: `(...)` (cannot nest) **and** `;` to end-of-line (both supported).

## `modbus_slave.py` — Modbus RTU slave (readback channel)
The Expert is Modbus master; the PC is the slave. Logs every frame the controller sends, with the hi/lo
byte split (each `#var` = 1 byte; 2 vars per register; little-endian within a register).
```
python modbus_slave.py --port COM6 --baud 115200 --slave 1
```
Then run a macro that does `MSETDATA[...]` and watch the frames arrive.

## `orchestrator.py` — instrument + push + watch (job progress readback)
Injects checkpoint pushes into a job at `(CKPT ...)` markers (+ auto start/done), pushes it to CNCDISK over
SMB, and watches the slave for checkpoints → reports how far the job got. **Only for instrumented progress
tracking; not needed for normal jobs.** Checkpoints must sit at SAFE points (never mid-cut — `MSETDATA`
briefly stalls the parser).
```
python orchestrator.py --self-test                                  # offline logic check
python orchestrator.py instrument job.nc -o job.instr.nc            # offline
python orchestrator.py run job.nc --port COM6 --ip 192.168.0.99     # instrument+push+watch
```

---

## Test macros
| file | safe? | what |
|---|---|---|
| `MODBUS_TEST.nc` | ✅ safe (no motion) | pushes `#200..#203 = 11,22,33,44` via `MSETDATA` — first-contact test |
| `CHECKPOINT_TEST.nc` | ✅ safe (no motion) | the proven readback pattern — sets `#250=1/2/3`, `MSETDATA` each |
| `MGETDATA_TEST.nc` | ⛔ **DO NOT RUN** | blocking `MGETDATA` wedged the analyze channel (needed a reboot) — kept only as a reference |

## ⚠️ Hazards (learned live — each cost a reboot)
- **Never read `#1630-#1636`** (analyze-channel status) from a running job — it wedges the parser; Reset
  won't clear it, only a reboot. The linter flags this (`E-CH1630`).
- **Single-channel `MGETDATA`** can block ~16 s and wedge the channel. Use `MSETDATA` push + checkpoint
  sentinels for readback instead.
- The safe readback = **checkpoint sentinels** (ordinary user vars + `MSETDATA`), never executor internals.

## Controller setup (one-time, on the panel)
1. `#279 Modbus RTU` → enable (Admin `777777`), `#267 Serial-2 baud` = `B115200`, reboot.
2. Wiring (port 2, DB9): SABRENT **3→7** (RXD2), **2→8** (TXD2), **5→9** (GND). Only those 3 pins; avoid 1/6 (5V).
3. `#284 Network boot mode` = `manu`; set Cable IP `192.168.0.99`, Host IP `192.168.0.100`; reboot.
4. `Pr76` (Macro Enable) = **Open** (required to run any macro).
