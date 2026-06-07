# DDCS Expert (M350) — Findings (the real target)

**Machine:** DDCS Expert M350 on the Ultimate Bee 1010 (studio). **Not on the home LAN.**
Most knowledge here is from **documentation** (official Expert manual + Russian community Modbus
docs + a scope capture), so much is `[CONFIRMED via docs]` / `[VERIFY ON MACHINE]` rather than
bench-proven. **Do not assume V4.1 findings carry over** — see [`../README.md`](../README.md).

> Tags: `[CONFIRMED]` · `[CONFIRMED via docs]` · `[VERIFY ON MACHINE]` · `[TO TEST]` · `[HYPOTHESIS]`.

---

## Serial = Modbus RTU ⭐ (the rich channel, Expert-only)
- RS232 port is **MAX3232, ±6V true RS-232** (scope-confirmed +8V=0/−8V=1) → the **SABRENT FTDI
  cable is the correct adapter.** `[CONFIRMED via docs + scope]`
- **Data is on port 2** (TXD2/RXD2). **Port 1 (TXD1/RXD1) = M3K keyboard** (reserved). 8N1, no parity.
  Controller is Modbus **MASTER** by default. `[CONFIRMED via docs]`
- Macros (run from G-code):
  - `MSETDATA[X1,X2,X3,X4,X5,X6]` — write controller vars #50–#499 → slave registers.
  - `MGETDATA[...]` — read slave registers → vars #50–#499.
  - Args: X1=start var, X2=slave#, X3=start **register address**, X4=length in **bytes** (reg=2 bytes),
    **X5 = Modbus function code** (16=write-multiple per the MSETDATA example; 1=read in the MGETDATA
    example), X6=var receiving the **exception code** (0=OK). Controller pauses ~16 s for a reply.
  - ⭐ **Each var #50–#499 carries exactly ONE byte (decimal 0–255)** — `MSETDATA` byte-packs them
    two-per-register. To move a value >255 (e.g. an error code), split/join with **`MDATA2BYTE`** /
    **`MBYTE2DATA`** across consecutive vars. `[CONFIRMED via RU manual `Инструкция.txt` 2026-06-06]`
  - Manual example: `#200=7 #201=8 #202=9 #203=10` → `MSETDATA[200,1,5,4,16,300]` (4 bytes → 2 regs @ addr 5).
  - Function codes: 01H coils, 02H discrete in, 03H holding, 04H input.
  - **PC slave ready:** `tools/modbus_slave.py` (pymodbus 3.13) logs every frame + the hi/lo byte split of
    each register; `tools/MODBUS_TEST.nc` is a motion-free push test. Run: `--port COM6 --baud 115200 --slave 1`.
- Scope capture confirmed `MSETDATA[200,1,6,12,15,300]` transmits #200…#203 as Modbus frames. `[CONFIRMED via scope]`
- ⭐⭐ **LIVE Modbus PC↔Expert CONFIRMED 2026-06-06** (CNC-FAIRY COM6 ↔ port 2, pymodbus 3.6.9 slave):
  `MSETDATA[200,1,0,4,16,300]` with `#200..#203 = 11,22,33,44` arrived as **WRITE HOLDING addr=0 =
  [5643, 11297]**. ⇒ confirmed: **115200 8N1, slave id 1; X5=16 → write-multiple HOLDING regs; X3 = register
  address; byte packing is LITTLE-ENDIAN within a register (first var = LOW byte, next = high).** So reg =
  `#(n+1)<<8 | #n`. The PC-slave readback channel is proven end-to-end. (pymodbus 3.13 broke the classic
  datastore — **pin `pymodbus==3.6.9`**.)
- **Homebrew architecture:** PC runs a **Modbus SLAVE**; the DDCS (master) pushes status vars (#200+,
  incl. error/exception) via `MSETDATA` and reads commands via `MGETDATA`. Bidirectional, documented.

### Params — read off the real machine `[CONFIRMED on machine 2026-06-06, fw 2025-06-19-00]`
Photographed the **System → param list** on the studio Expert (model **DDCSE-5T-standard**, panel
"DDCS Expert V1.1", **Software Ver 2025-06-19-00**, HW 2021-1213-23). Confirmed numbers on THIS firmware:

| # | Name (as shown) | Value seen | Notes |
|---|---|---|---|
| `#266` | **Serial 1 baud rate** | `B115200` | Serial 1 = M3K keyboard port |
| `#267` | **Serial 2 baud rate** | `B115200` | **Serial 2 = Modbus data port** |
| `#268` | **External keyboard type** | `other` | set to `M3K` to enable the M3K keypad (port 1) |
| `#278` | USB keyboard type | `keyboard` | |
| `#279` | **Modbus RTU** | `NO` | ⭐ **RESOLVED: #279 IS the Modbus-RTU enable** (not "Barcode file location" as the official manual claimed) — set to enable Modbus |
| `#284` | **Network boot mode** | `Close` | ⭐ set to **manu-IP** to bring the Ethernet up (Cable IP shows "Disconnect" while Close) |
| `#296` | **Serial 2 Parity method** | `None` | → Serial 2 = **8N1** |
| `#297` | **Serial 2 Stop bits** | `1` | → Serial 2 = **8N1** |

⇒ Modbus port-2 framing is confirmed **115200 8N1** straight off the panel. "Restart takes effect" for
network/serial params. The Param page has a **Search** soft-key and a **`#50-#499`** (uservar) viewer.

- **Reboot** after serial/network param changes. `[CONFIRMED via docs + panel note "Restart takes effect"]`

## Firmware internals (Expert NAND backup `nand1-1`, static analysis 2026-06-06)
From the `ddcs-expert` skill's `firmware-backup-2025-12-31/.../nand1-1/`. Expert SoC ≠ V4.1
(W55FA93/ARMv5): the Expert uses **i.MX-class UARTs** — `/dev/ttymxc1`, `/dev/ttymxc2` — plus
`/dev/ttySP0`, `/dev/ttySP1`. (Ghidra: ARM LE; confirm core from the ELF header — likely ARMv7.)
- **`parse.out`** (~2.9 MB, the Expert app/parser) — **handles Modbus serial in *userspace*** (unlike
  V4.1, whose app has no serial). Opens `ttymxc1`/`ttymxc2`, sets baud via `cfsetispeed`/`cfsetospeed`;
  strings: `OpenSERIAL01/02`, `SetupSerial`, `Enter Uart0/Uart1 modbus communication`,
  `Uart0/Uart1 modbus parameter address err`. ⇒ the documented `MSETDATA`/`MGETDATA` channel is here and
  **decompilable in Ghidra** to pin the exact **port↔Uart mapping, baud, and frame format**. `[lead]`
- **`pidMonitor.out`** (~0.6 MB) — process/watchdog monitor; not serial-relevant.
- **M3K keypad: NOT in userspace** — `parse.out` reads `/dev/input/event*` (no `M3K`/keypad strings),
  same as V4.1's `ddcsv4.out`. ⇒ the M3K serial→keystroke driver is **kernel-level on the Expert too**;
  its protocol is **not recoverable** from these binaries (would need the kernel/rootfs partition or a
  real M3K to sniff).
- ⇒ **Trigger reality:** M3K-serial is a dead end on both controllers (kernel-level). **Expert autonomy
  = `sysstart` (boot) + Modbus (`parse.out`, real & decompilable) + `#2037`.** V4.1 = **External Start
  input** (hardware).

## RS232 connector pinout + wiring `[CONFIRMED via manual]`
DB-9 **female** on the controller (manual §4.7, `assets/Modbus_RS232_DDCSE/Распиновка разъёма.pdf`):

| Pin | Signal | Pin | Signal |
|---|---|---|---|
| 1 | 5V | 6 | 5V |
| 2 | **RXD1** | 7 | **RXD2** |
| 3 | **TXD1** | 8 | **TXD2** |
| 4 | (not connected) | 9 | GND |
| 5 | GND | | |

- **Modbus (PC↔Expert) = port 2, 3 wires (bidirectional):** SABRENT **TX(3)→RXD2(pin 7)**,
  **RX(2)←TXD2(pin 8)**, **GND(5)↔GND(pin 9 or 5)**. MAX3232 ±6 V → SABRENT correct.
- **M3K keypad = port 1** (RXD1 pin 2 / TXD1 pin 3), enabled by **`#268 = M3K`** at **115200**
  (`#266`/`#267`). ⇒ **the M3K runs at 115200** — first hard number on the keypad (protocol still
  kernel-level, but baud is known now). `[CONFIRMED via manual]`
- Note: this pinout (RXD1=2, TXD1=3, RXD2=7, TXD2=8) is the authoritative one; the V4.1 send-tests
  used RXD1=3 (which is actually TXD1) — invalid pin — though V4.1's M3K is kernel-level anyway.

## Network (differs from V4.1)
- Expert supports **manual IP only**. Defaults: controller `192.168.0.99`, host `192.168.0.100`.
- `#284 "Network boot mode"` options are **`Close` / `auto` / `manu`** — set to **`manu`** (static),
  then System Set → "Set IP Addr" (Cable + Host). **Restart takes effect.** `[CONFIRMED on machine 2026-06-06]`
  - While `#284=Close` the cable NIC is **off** (System Info shows "Cable IP: Disconnect" and the
    Cable-IP field is uneditable). Setting `manu` + reboot brings it up. The PC NIC stays
    `Disconnected` (link-down) until the controller NIC powers on.
- `network.conf` (on SYSDISK) stores the manual IPs as plain text (line2=Cable IP, line3=Host IP).

## ⭐ SMB file access — CONFIRMED on the real machine `[CONFIRMED 2026-06-06, fw 2025-06-19-00]`
The **V4.1 SMB recipe works as-is on the Expert** (PC reads/writes the controller's disk). Setup that worked
on the studio Toughbook **CNC-FAIRY** (fresh Win11): static `192.168.0.100/24` on the wired NIC; enable SMB1
client + `EnableInsecureGuestLogons $true` + `BlockNTLM $false` (admin + reboot); then
`net use \\192.168.0.99\IPC$ /user:guest ""` and **map the shares to drive letters** (raw-UNC
`Test-Path \\ip\sysdisk` is flaky under SMB1-guest — `net use S: \\192.168.0.99\SYSDISK` works).
- Shares: **`CNCDISK`** + **`SYSDISK`** (same names as V4.1). Server = "Arm Linux Samba Server", netbios `CNC-PDA`.
- **`smb.conf`** (read off SYSDISK): `security = share`, **`guest account = root`** (guest = full root access),
  **`SYSDISK → /mnt/nand1-1/`** (the same `nand1-1` mount as the firmware backup — `parse.out` lives here),
  **`CNCDISK → /local/`**, both **`writeable = yes`**.
- **Read AND write CONFIRMED** end-to-end (round-trip write/read/delete on CNCDISK from the PC).
- ⇒ The PC↔Expert file channel is fully bidirectional — the V4.1 dispatcher trick (overwrite a loop file
  over SMB) should port directly. Net Disk (controller-mounts-PC) is a *separate* option, not needed for this.
- **`uservar` lives on CNCDISK** here (`/local/uservar`, **3601 B = 450×f64 + 1 trailing byte**), NOT on
  SYSDISK as on the V4.1 (3200 B). **Slot map `slot = #var − 100` CONFIRMED** by decoding live values over
  SMB (operator test writes 111/222/…/888 landed exactly on `#150,#151,#200,#250,#350,#450,#520,#521`).
  ⇒ **Expert `uservar` range = #100–#549** (450 slots; bigger than V4.1's #100–#499). The PC reads controller
  state by decoding this file as little-endian f64 — `[CONFIRMED readback 2026-06-06]`. Slot 0 = byte 0 (no header).
- Run-state hidden files exist on SYSDISK: per-program **`.<name>.nc.pos`** (60 B each) and **`.break0/.break1`**
  (breakpoint-resume) — same family as the V4.1 run-state files. `[TO TEST what they track]`

## ⚠️ Dispatcher: Expert `M47` ≠ V4.1 `M47` — the V4.1 loop trick does NOT port `[CONFIRMED 2026-06-06]`
The V4.1 software dispatcher relies on `M47` = **"restart program from top"** (firmware built-in) so an
`M47` self-loop re-reads the file each cycle. **On the Expert, `M47` is a different macro entirely** —
defined in the `slib-m.nc` M-code library as `O10047`, a **count-and-conditionally-pause** routine:
```
O10047  #701=#701+1  #702=#702+1  #1506=47
        IF #702==#703 GOTO1  / GOTO2
   N1   #702=0  #1505=1(msg)  #1620=1(pause/feed-hold)  G04 P500
   N2
```
### "M99 loop?" — RESOLVED by static analysis 2026-06-06: the file-overwrite dispatcher does NOT port
Question: is there an Expert construct that **re-reads the job file from disk each cycle** (the property the
V4.1 `M47` self-loop dispatcher depends on, so a PC SMB-overwrite injects new code)? Answer: **no confirmed one.**
- **DDCS loops = `IF/GOTO N<label>`** (CORE_TRUTH-confirmed) → these re-execute the **already-loaded** code
  in RAM; a PC file-overwrite is invisible to a running looped program. Same for an `M99` main-loop.
- **`M98 P<n>` resolves an `O<n>` label from the loaded libraries in RAM**, NOT a per-call disk read —
  proven: `sysstart`'s `M98 P501` → `O501` lives in `slib-g.nc` (a boot-loaded library), and `O501` is the
  per-axis homing/zero-search sub. So an `M98`-loop dispatcher also won't see overwrites (for library subs).
- **No `slib-m.nc` M-code restarts/re-selects the program** (all are plain `M99`-terminated subs); `M47` is
  the count/pause macro above, byte-identical in the factory backup.
⇒ **Do NOT port the V4.1 file-overwrite/self-loop dispatcher to the Expert.** The only file-based path that
re-reads disk is a **per-cycle Start trigger** (V4.1 confirms Start re-reads the file) — i.e. not zero-touch.
**For true autonomy on the Expert, use the documented design instead:** `sysstart.nc` boot-bootstrap +
**Modbus `MGETDATA`** (controller pulls commands from the PC slave — live inbound, no file hack) + SMB for
job-file delivery + `uservar`/`MSETDATA`/`error.nc` for readback. (Modbus blocked on the ferrule.)

## Macro / param internals over SMB `[CONFIRMED 2026-06-06]`
- **`setting` file = 1000×f64, index = param #** (8000 B). Decodes over SMB and matches the panel:
  baud code **4 = B115200**; `#284` Net-boot **0=Close / 1=auto / 2=manu**; `#296`=0 (parity None),
  `#297`=0 (1 stop bit) → 8N1. WCS offsets live here too (`#805+[WCS−1]*5`). ⇒ PC can read **all persisted
  config + WCS**, not just `uservar`. (`#325`=garbage here — param numbering is controller-specific.)
- **`slib-m.nc` = M-code library:** each M-code → subprogram **`O(10000+code)`** (M0=O10000 … M30=O10030,
  M47=O10047, M50-M62=O10050-62). User-overridable. `M30` (O10030): `M5 M9 M11` + conditional return to
  `Z#569`/`X0Y0` per `#730`. **`slibuser.nc`**: user G-code `G199` = `G90 G01 X#6Y#7Z#8 F#15`.
- `parse.out` (live, 2.99 MB) references `sysstart.nc` + `M30` as strings (boot hook real). `MSETDATA`/
  `MGETDATA` are NOT plain-ASCII in it (wide-char/tokenized?) — revisit when wiring Modbus.

## System / macro variables (read off the operator's live macros 2026-06-06) `[CONFIRMED on machine]`
From `READ_VAR.nc`, `COPY_WCS.nc`, `SAVE_WCS_XY_AUTO.nc`, `sysstart.nc` on this machine:
- `#578` = **active WCS number** (1=G54 … 6=G59).
- `#880` / `#881` = **current machine X / Y position**. (`sysstart` does `#883=#881` for gantry A←Y sync.)
- **WCS offset block:** base `= 805 + [WCS−1]*5`; within a block **X=base, Y=base+1, A=base+3**
  (G54 = #805–809, G55 = #810–814, …). `#1518` = "A homed" flag.
- **On-screen message:** `#1505 = -5000(text with %f)`, args in `#1510` / `#1511`.
- **Numeric input prompt:** `#2070 = <var>(prompt text)` — pauses for operator entry into that var.
- Indirect addressing works: `#[#100]` reads the var whose number is in `#100` (used for the var-reader).
- More vars from `slib-m.nc`: `#1506` = current M-code indicator, `#1620` = **feed-hold/pause flag**,
  `#701/#702/#703` = counter / counter / limit (M47 count macro), `#730` = end-of-program return mode
  (0/1/2), `#569` = safe-Z return height, `#624` = G53 Z return. `IF/GOTO/Nlabel` + `G04 P<ms>` dwell.

## Control
- `#2037` **virtual buttons** press any of 201 panel functions from a running macro
  (`#2037 = 65536 + [KeyValue − 1000]`). `[CONFIRMED]` per the `ddcs-expert` skill
  (`Virtual_button_function_codes_COMPLETE.xlsx`). Subject to the one-program-at-a-time rule.

## Autonomy outlook — the Expert is a superset of the V4.1
The V4.1 bench proved a **software dispatcher**: an `M47` self-loop re-reads its file from disk each
cycle, so the PC injects jobs by overwriting the loop file over SMB (one bootstrap Start needed).
**⚠️ That specific trick does NOT port — see "M99 loop? RESOLVED" above** (`M47` is redefined; `IF/GOTO`
and `M98` loop in RAM, not from disk). The Expert reaches autonomy a **different, documented way** — and
still with **zero added hardware**:
- **Zero-touch bootstrap:** `sysstart.nc` auto-runs at boot → it can launch the `M47` dispatcher with
  no manual/External Start at all. `[CONFIRMED via docs that sysstart auto-runs; dispatcher TO TEST]`
- **Second inbound channel:** Modbus **`MGETDATA`** (controller pulls commands from a PC slave) — a
  live bidirectional path independent of the file trick. `[CONFIRMED via docs]`
- **Real fault readback:** `error.nc` fires "when system abnormal working." `[CONFIRMED via docs]`
- **Panel control:** `#2037` virtual buttons. `[CONFIRMED]`

**Plan:** develop + harden the dispatcher and PC orchestrator on the V4.1 (safe, working), then deploy
to the Expert. **Verify on the actual machine `[TO TEST]`:** file-reload / `M47`-reread holds here;
`sysstart` sustains the loop; SMB disk access vs Net-Disk-only; which system var holds the alarm code.

## Macro hooks — official install-file description `[CONFIRMED via docs]`
From the DDCS-Expert "install file description". These auto-run / are invoked by the firmware:
- **`sysstart.nc`** — *"Boot initialization file — can modify it."* Auto-runs at **boot**. This is the
  Expert's hands-free entry point (the dispatcher-bootstrap candidate). **Absent on V4.1.** **Operator-
  customizable, and HAS been customized on this machine** — the live file read 2026-06-06 is *not* the
  factory default. Factory default (per docs) was `M115` (built-in homing) → `G04 P1.0` → sync. The
  **current live `sysstart.nc`** (operator-modified) homes each axis via a subprogram instead:
  ```
  (Start Homing Sequence)
  M98 P501 X2   (Home Z)
  M98 P501 X0   (Home X)
  M98 P501 X1   (Home Y)
  #883 = #881   (gantry sync A<-Y, after motion stops)
  #1518 = 1     (mark A homed)
  M30
  ```
  ⇒ confirms `sysstart.nc` auto-runs at boot AND is freely editable — **the place to bootstrap a
  PC-fed dispatcher**. `M115`/`M98 P501` are Expert homing; the **V4.1 has no `M115`** (`G128`/`M105-108` there).
- **`error.nc`** — *"When system abnormal working, system will execute this file."* A **system-fault /
  alarm** hook (NOT a G-code syntax-error hook — see V4.1 findings; program errors won't trigger it).
- **`pause.nc`** (pause), **`key-1.nc`…`key-7.nc`** (K1–K7), **`ext_button.nc`** + **`extnc0/1/2-N.nc`**
  (self-design buttons: release / short-press / long-press), **`probe.nc`**, **`fndX/Y/Z/A/B.nc`** +
  **`fndzero.nc`** (go home), **`gotozero.nc`** (go work zero), **`T.nc`/`ALL_T.nc`** (tool change),
  **`slib-g.nc`/`slib-m.nc`/`slibuser.nc`** (G / M / user libraries), **`absX..B.nc`**.
- `advstart.nc` is **not** in the Expert list (it's a V4.1 file — the "Advanced Start" feature).

## ⭐ Run-state / alarm system variables — the readback backbone `[CONFIRMED via variable-map xlsx 2026-06-06]`
From `DDCS_Variables_mapping_2025-01-04.xlsx` (skill), cross-checked against `slib-m.nc`/`slib-g.nc`:
- **`#1630`–`#1636` = Analyze channel 1–7 STATUS: `-1` Idle / `0` Working / `1` Pause** (the executor's
  run-state). **⚠️⚠️ DANGER: reading `#1630` from inside a running program WEDGES the analyzer** — froze
  "analysis" hard, Reset would not clear, **required a reboot** (observed 2026-06-06, `PUSH_RUNSTATE.nc`
  froze *before* its MSETDATA — slave got nothing). DO NOT read `#16xx` analyze-channel internals from a
  normal job. Reading one's *own* channel status is self-referential and locks the parser. A cross-channel
  watchdog *might* read another channel's status, but that's unproven and risky — **do not blind-test it
  live** (each wedge = a reboot). Treat `#1630` as write-only-by-firmware for now.
- **`#1620`–`#1626` = Analyze channel 1–7 EXECUTION method:** `0`=Start/Restart, `1`=Internal Pause,
  `2`=External Pause. Writing these *commands* a channel. ⇒ corrects the earlier note: `M47` (`O10047`)
  does `#1620=1` = "request internal pause on channel 1" (not a generic feed-hold flag).
- **Servo alarm signals:** `#1000`(X) `#1003`(Y) `#1006`(Z) `#1009`(4th) `#1012`(5th); system alarm out `#1236`.
- Per-axis analyzing-vs-manual mark: `#1800`–`#1804`. Error key-indicator: `#1931`.
- ⚠️ **The Expert has 7 parallel "analyze channels."** This is the architecture for a non-blocking watchdog:
  run the job in one channel, a status-pusher in another. **Single-channel readback is dangerous** — the
  `MGETDATA`/`MSETDATA` ~16 s blocking wait can **wedge the channel hard enough to require a reboot**
  (observed 2026-06-06: a bad test macro froze "analysis", Reset would not clear it). `[CONFIRMED]`
- **NOTE:** no single "last syntax-error code + line" variable was found in the map. The on-screen
  System Log shows `syntax error: Ln` but is **not** persisted to a readable file (checked SYSDISK/CNCDISK
  mtimes after a live syntax error — nothing updated). ⇒ exact syntax-error text/line is **not** directly
  remotely readable; detect via run-state (`#1630`) + checkpoint sentinels + `.pos` (did-it-run) instead.
- **`.<name>.nc.pos`** is created/updated only when a program actually RUNS (errored-at-parse programs
  leave none) → a pollable "did it execute" flag over SMB. `[CONFIRMED 2026-06-06]`

### ✅ The SAFE readback pattern (proven, no wedge) — use this, not system-var reads
`MODBUS_TEST.nc` proved that a program setting **ordinary user vars to known values** and `MSETDATA`-ing
them transmits reliably and never wedges. So the readback design is **checkpoint sentinels**, NOT reading
executor internals:
- The PC-pushed job sets `#250 = <checkpoint id>` then `MSETDATA[250,1,0,2,16,300]` at safe points
  (after header, after each phase, just before `M30`). The PC slave sees how far it got — last checkpoint
  received = last line reached before any stop/error. No system-var reads → no wedge.
- A **syntax error** means the job never runs → zero checkpoints arrive AND no `.pos` is written → PC
  infers "failed to parse." (Exact line still only on the System Log screen.)
- **Hardware/system alarms:** route through **`error.nc`** (fires on "system abnormal") — have it set a
  user var and `MSETDATA` it. `[TO TEST carefully — error.nc content + whether MSETDATA is safe there]`
- Reading plain I/O/alarm vars like `#1000` may or may not be safe — **untested in isolation** (the
  PUSH_RUNSTATE wedge read `#1630` first, so we can't blame `#1000` yet). Don't blind-test live.

## Error-readback options (ranked)
1. **Serial Modbus (best):** a `sysstart`/dispatcher macro periodically `MSETDATA`s the alarm/status
   vars to the PC slave. `[VERIFY which system var holds the live alarm code.]`
2. **Net Disk flag file:** `error.nc` writes a status value to a file landing in the PC's `share`
   folder; PC polls it locally. `[VERIFY a macro can write to Net Disk.]`
3. Re-test the V4.1 findings here (syntax-error sentinel, `.env` line-number field) — `[TO TEST]`.

## Assets in this folder
- `assets/Modbus_RS232_DDCSE/` — `M350 modbus manual RU.docx`, `Инструкция.txt`, connector pinout
  (`Распиновка разъёма.pdf`), bundled **Termite** terminal (`Termite_1.0.0.6/`, has a Modbus scanner).
- `assets/Modbus_RS232_DDCSE.rar` — original archive. `assets/RS232-DDCSE осциллограмма.pdf` — scope capture.

## Open actions
- [x] ~~Confirm SMB read of `uservar`/`error.nc`~~ — **DONE 2026-06-06**: full SMB **read+write** confirmed
      (V4.1 recipe works; CNCDISK=/local/, SYSDISK=/mnt/nand1-1/, guest=root, writeable). See SMB section above.
- [x] ~~Identify real param numbers for Modbus-RTU enable + port-2 baud~~ — **DONE**: `#279`=Modbus RTU,
      `#267`=Serial-2 baud (115200), `#296`/`#297`=Serial-2 parity/stop (8N1). See param table above.
- [x] ~~Confirm `uservar` slot layout~~ — **DONE 2026-06-06**: `slot=#var−100`, range **#100–#549** (450×f64). See SMB section.
- [ ] **Serial BLOCKED — needs a proper ferrule** to land pins 7/8/9. Then: wire SABRENT to port 2, find its COM on CNC-FAIRY, enable `#279`=Modbus, reboot.
- [ ] Stand up a PC Modbus slave (`pymodbus`); confirm `MSETDATA` pushes #200+ to it.
- [ ] Find the system var holding the live alarm code → log *which* error.
- [ ] Port the V4.1 `M47` dispatcher to `sysstart.nc` here (file-reload trick over SMB) — **safety first** (E-stop).
