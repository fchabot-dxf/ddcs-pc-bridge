# DDCS v4.1 — RS232 / Serial Probe Notes

_Last updated: 2026-06-06_

## 🚦 HANDOFF — START HERE (Claude Code / next session)

**Goal:** read DDCS error/status on the PC, eventually drive the machine. Bench unit = **DDCS V4.1 @ 10.0.0.50**. Real target = **DDCS Expert M350** (Ultimate Bee).

**WORKS NOW — V4.1 file access over Ethernet (full read/write/delete):**
- Shares: `\\10.0.0.50\cncdisk` (work disk, G-code) and `\\10.0.0.50\sysdisk` (system folder).
- **Connection recipe (PC, one-time):** SMB1 client installed; `Set-SmbClientConfiguration -EnableInsecureGuestLogons $true -Force`; `Set-SmbClientConfiguration -BlockNTLM $false -Force`; then **`net use \\10.0.0.50\IPC$ /user:guest ""` FIRST**, then the shares open. Controller params already set (#325 network ON, #327=10.0.0.50, #328=255.255.255.0, #329=10.0.0.1, #330=10.0.0.34); network param changes need a reboot.

**CONFIRMED facts:**
- `uservar` (3200 B, SYSDISK) = 400 little-endian f64; **slot = (#var − 100)**, covers #100–#499. High vars (#1505) NOT stored here. Slots 390–392 = live coords #490–492.
- `setting` = 1500 f64, positional by param #; IPs stored as raw octet bytes at #327–330.
- **Serial = Modbus, M350-ONLY** (V4.1 firmware has zero Modbus — checked 2 builds). M350: enable `#279` Modbus RTU, baud `#267`, data on **port 2** (port 1 = M3K keyboard), MAX3232 ±6V true RS-232 → SABRENT cable is correct. `MSETDATA`/`MGETDATA` r/w slave registers using vars #50–#499. Docs: `controllers/expert-m350/assets/Modbus_RS232_DDCSE/`.

**ACTIVE TEST B — error readback (ARMED, not yet confirmed):**
- Controller `error.nc` currently = `#200 = 8888` (original empty version: `controllers/v4.1/assets/error.nc.bak`).
- Baseline: `uservar` slot 100 (=#200) currently = 22222 (from MAP_PROBE).
- **To confirm:** trigger ANY fault → controller runs error.nc → #200=8888 → re-read `\\10.0.0.50\sysdisk\uservar` slot 100; if it reads 8888, error-readback works end-to-end.

**NEXT STEPS:**
1. Trigger a fault, confirm Test B (slot 100 → 8888).
2. Find the system var holding the live **alarm code** so error.nc records *which* error (write it into a #100–#499 var).
3. Build PC-side poller that watches the uservar slot over SMB — first real app (per `fred-app-architecture`, likely a small app under `C:\Users\danse\APPS`).
4. Restore pristine `error.nc` from `controllers/v4.1/assets/error.nc.bak` when done testing.

**TRIGGER / EXECUTION (open question — Fred):** Ethernet can read/write files but **can't press Start**; `#2037` virtual buttons only fire while a program already runs. Trigger options from cold idle: (a) `sysstart.nc` auto-runs at boot → launch a persistent dispatcher loop that reads Ethernet command files + fires `#2037` (zero serial — preferred if loop sustains); (b) **RS232 port 1 = M3K keyboard input**, read even at idle → emulating M3K keystrokes can press Start/navigate as hardware input with NO running program (the one thing Ethernet can't do; should work on V4.1 too since it's the keyboard port, not Modbus). Cost of (b): M3K serial protocol is undocumented → reverse-engineer from firmware or sniff a real M3K (skill experiment B1).

**FRED'S PREFERRED DIRECTION (2026-06-06):** use **serial for the trigger/control**, even on the V4.1.
Plan: **Ethernet = data** (push G-code, read status/uservar); **serial port 1 (M3K keyboard) = trigger**
(emulate pendant → press Start/select/navigate from outside, no running program, no dispatcher needed —
cleanest control path on V4.1). TODO: (1) recover M3K protocol = baud + key→byte map, either by analyzing
`controllers/v4.1/assets/system-backup/current/ddcsv4.out` (skill exp B1) or sniffing a real M3K with scope/Termite;
(2) wire **PC TX → controller RXD1** (port 1) for sending; (3) verify port-1 voltage level (likely
MAX3232 ±6V true RS-232 like port 2 → SABRENT OK; if 5V TTL, need a TTL adapter). First Claude Code task:
grep/analyze ddcsv4.out for the keyboard serial handler + key-code table.

**BACKUPS:** full system snapshot in `controllers/v4.1/assets/system-backup/current/` (79 files, pristine error.nc). Leftover test files on CNCDISK: `PC_PUSH_TEST.nc`, `MAP_PROBE.nc` (harmless; delete anytime).

---



## Goal
See whether a loaded G-code job **errored** (and which error) on the PC, and eventually drive the
controller from software. The serial port is the "lottery ticket" channel — high upside, unknown if
it broadcasts anything.

## What we've confirmed so far

### The USB-to-serial cable
- **SABRENT USB 2.0 to Serial DB-9 RS-232, FTDI chipset** (purchased May 31, 2026).
- It's a **true RS-232** adapter (±12V signaling), **not** 5V TTL.
- PC recognizes it: shows up in Device Manager as **"USB Serial Port (COM4)"**, manufacturer **FTDI**.
  Driver already installed — no setup needed.
- **Port number to remember: COM4.**
- Connector is **DB9 male**.

### The controller port
- Port on the DDCS v4.1 is labeled **"HMI/RS232 串口"** (串口 = serial port).
- Because it says **RS232**, it runs at true RS-232 levels → **the SABRENT cable is the correct type.**
- It's a **DB9** connector (appears female / sockets — confirm by eye; male cable + female port mate
  directly).

### Pinout silkscreened next to the port
```
9          5
GND        GND
TXD2       TXD1
RXD2       RXD1
5V         5V
6          1
```
This port carries **two serial channels** (TXD1/RXD1 and TXD2/RXD2) **plus 5V power pins** — it is
**NOT** wired like a standard PC serial port.

## The catch — do NOT just mate the two DB9s
On a normal PC serial port the data lives on pins 2 and 3. On this controller those spots are taken
by **5V power** and the **wrong channel**. If you plug the cable straight in, your cable's receive
line lands on the controller's **5V pin** — it won't listen, and it risks feeding 5V where we don't
want it.

## Safe way to probe (listen-only)
Connect only **two wires** using a DB9 breakout or jumper wires:
1. Controller **TXD1** → cable's **RXD (pin 2)**
2. Controller **GND** → cable's **GND (pin 5)**
3. Leave the cable's **TXD (pin 3)** disconnected — listen-only = zero risk of pushing voltage into
   the controller.

Then run a serial monitor on **COM4**, sweep common baud rates (9600 → 115200 → 38400 → 57600 →
19200), and watch for bytes while pressing panel buttons / triggering a fault.
- Readable/structured bytes = jackpot (status/error stream).
- Garbage at every baud = swap TX/RX.
- Total silence = port is likely input-only (expects key codes, doesn't broadcast). Fall back to the
  Ethernet route.

## The easier alternative (the actual reliable path)
**Ethernet/SMB + `error.nc` hook** — no serial, no risky wiring, no extra parts:
- The Ethernet port is an SMB file share; the PC reads/writes files on the controller.
- `error.nc` is a user-editable macro the controller runs on fault. Add a line that writes a
  persistent variable (serializes to a file the PC polls over the share) and/or raises a spare output.
- This is the intended, confirmed-feasible path to "see errors on the PC."

## ⚠️ MAJOR UPDATE (2026-06-06) — serial is NOT dead; it's Modbus, transmit-on-command
Fred supplied `controllers/expert-m350/assets/Modbus_RS232_DDCSE.rar` + `controllers/expert-m350/assets/RS232-DDCSE осциллограмma.pdf`
(scope capture). Decoded findings:
- The DDCS **Expert** RS232 port is a **Modbus** interface at **true RS-232 levels (±8V** confirmed on
  the scope: +8V=logic0, −8V=logic1) → the SABRENT true-RS232 cable is the CORRECT adapter.
- A macro **`MSETDATA[200,1,6,12,15,300]`** transmits DDCS system variables (#200,#201,#202,#203…)
  out the port as Modbus frames. Scope shows live values e.g. #200=7,#201=8,#202=9,#203=10.
- **The "receive-only" conclusion below was WRONG.** The port doesn't stream on idle — it transmits
  only when a macro like MSETDATA runs. Our V4.1 listen test caught silence because no transmit macro
  was running, not because the port can't transmit.
  RAR extracted to `controllers/expert-m350/assets/Modbus_RS232_DDCSE/` — `M350 modbus manual RU.docx`, `Инструкция.txt`,
  `Распиновка разъёма.pdf` (connector pinout), Termite terminal + Modbus PDFs.

### CONFIRMED M350 Modbus recipe (M350 manual + Инструкция.txt)
- Port = **MAX3232**, **±6V true RS-232** (−6V=1, +6V=0, idle high). **8N1**, no parity. Default MASTER.
- **`#279` "Modbus RTU"** = enable switch. **`#267`** = baud for **serial port 2** (2400/4800/9600/
  19200/115200). **Reboot after setting.**
- **DATA IS ON PORT 2 (TXD2/RXD2). Port 1 = M3K keyboard (reserved).** Explains our silent tests:
  TXD1 = keyboard port; TXD2 was silent only because #279 was off + no macro ran.
- Macros (from G-code): `MSETDATA[X1,X2,X3,X4,X5,X6]` writes DDCS vars #50–#499 → slave registers;
  `MGETDATA[...]` reads slave regs → #50–#499. X1=start var, X2=slave#, X3=start addr, X4=byte length
  (Modbus reg=2 bytes), X5=mode/func, X6=var holding exception code. Controller pauses ~16s for reply.
  Also `MBYTE2DATA`/`MDATA2BYTE`. Function codes: 01H coils, 02H discrete in, 03H holding, 04H input.
- **Homebrew architecture:** PC runs a **Modbus SLAVE**; DDCS (master) pushes status vars (#200+, incl.
  error/exception) via MSETDATA and reads commands via MGETDATA. Bidirectional, documented.
- **V4.1 status: CONFIRMED NOT SUPPORTED.** Checked the newest V4.1 firmware (`ddcsv4(2025-04-04)`)
  binary `ddcsv4.out`: 0 hits for SETDATA/GETDATA/"odbus"/MAX323; no Modbus/serial/baud labels in its
  `eng`/`rus` param files. Searched by FEATURE not param # (per Fred's point) — the macros simply
  aren't compiled into V4.1 firmware. **Modbus serial is an M350 (Expert)-only feature.**
- **Decision:** V4.1 bench → PC readback only via network/SMB (already on net at 10.0.0.50, needs SMB1
  client on PC). M350 Expert (real target) → Modbus serial channel (SABRENT cable is correct ±6V RS-232).

## ✅ V4.1 NETWORK/SMB ACCESS WORKING (2026-06-06)
Controller reachable at **10.0.0.50** ("Arm Linux Samba Server"). Full file READ access achieved.
**Shares: `CNCDISK`** (work disk, G-code; currently empty) and **`SYSDISK`** (system folder — has
`error.nc` [2 bytes/empty], `setting`, `ddcsv4.out`, `uservar` [3200B], all macros/param files).

### Access recipe (PC side, one-time; needed because controller is old SMB1 + guest + NTLM):
1. Controller params: #325 network enabled, #327=10.0.0.50, #328=255.255.255.0, #329=10.0.0.1,
   #330=10.0.0.34 (already set). Reboot. (Note: #325 "disable network" toggle was stubborn via UI;
   it IS enabled now since SMB works.)
2. PC: enable SMB1 client — `Enable-WindowsOptionalFeature -Online -FeatureName SMB1Protocol` then
   `...-FeatureName SMB1Protocol-Client` (parent first!), reboot.
3. PC (admin PowerShell): `Set-SmbClientConfiguration -EnableInsecureGuestLogons $true -Force` and
   `Set-SmbClientConfiguration -BlockNTLM $false -Force`.
4. Establish guest session FIRST (enumeration/access fails without it):
   `net use \\10.0.0.50\IPC$ /user:guest ""`  → then `\\10.0.0.50\cncdisk` and `\\10.0.0.50\sysdisk`
   open in Explorer / Get-ChildItem.

### Next steps for error-readback (not yet done):
- Confirm WRITE access (write a test file to CNCDISK, delete it).
- Populate `error.nc` to write an error/flag file the PC polls over SMB (the original goal).
- Push G-code to CNCDISK from PC.

## TEST PLAN — M3K serial TRIGGER over RS232 (V4.1, Fred's preferred control path)
**Premise:** Ethernet can't press Start; port 1 = M3K keyboard input is read even at idle, so emulating
M3K keystrokes over serial can trigger Start/select/navigate from the PC with NO running program and no
dispatcher hack. Goal of this plan: prove the PC can drive the V4.1 panel by sending M3K key codes.
Safe to test on the bench V4.1 (no motors). Confidence tags: [TO TEST] until a RESULT line is filled.

### T1 — Recover the M3K serial protocol (baud + key→byte map) [TO TEST]
**Method A (no hardware):** analyze the firmware binary `controllers/v4.1/assets/system-backup/current/ddcsv4.out` for the
keyboard/serial handler and the key-label table (CONT/STEP/ZERO/HOME/PROBE/MIDDLE/AUTO/MDI/Start/…);
cross-ref the port-1 (M3K) UART init for baud + framing. (= skill experiment B1.)
**Method B (hardware):** sniff a real M3K pendant with the scope/Termite; decode frames per keypress.
**Proves:** the exact bytes to send for each key, esp. **Start**.
**RESULT (T1):** baud=___  framing=___  Start code=___  Enter=___  arrows=___  file-select=___

### T2 — Confirm port-1 voltage level [TO TEST]
**Method:** with controller powered + idle, scope/meter **RXD1 (port 1)**. Idle true RS-232 sits at a
**negative** mark (~−6V via MAX3232); 5V TTL idles at +5V/high.
**Proves:** which adapter to use to SEND — SABRENT (true RS-232 ±) if RS-232; a USB-TTL adapter if 5V TTL.
**RESULT (T2):** idle level=___  → port type=___  → adapter=___

### T3 — Send one benign key, confirm panel reacts [TO TEST]
**Wiring:** PC **TX → controller RXD1 (port 1)**, GND↔GND. (Adapter per T2.) Leave other lines off.
**Method:** at the READY screen, send the byte(s) for a harmless key first (e.g., a page switch or an
arrow). Watch the DDCS screen change. Then test **Enter** / file navigation.
**Proves:** PC→controller keystroke injection works (the core of the trigger).
**RESULT (T3):** key sent=___  panel reacted? ___

### T4 — Full trigger: select + START a job from the PC [TO TEST]
**Method:** Ethernet-drop a safe motion-free `.nc` to CNCDISK → over serial send the keys to select it
on the file page → send **Start**. Confirm it runs (e.g., it sets a var visible in `uservar`, or screen
shows running). Combine with the error-readback hook to read outcome over SMB.
**Proves:** end-to-end PC control of the V4.1 using **Ethernet=data + serial=trigger**, no dispatcher,
no one touching the panel.
**RESULT (T4):** job started from PC? ___  outcome read back over SMB? ___

**Safety:** bench V4.1 only (no motors). NEVER auto-send Start on the spindle machine without an
independent hardware E-stop + watchdog (see skill safety section).

## Serial probe RESULT (2026-06-05) — [SUPERSEDED, see MAJOR UPDATE above]
Listen-only rig built: male breakout on controller, female breakout on SABRENT cable (COM4),
GND pin 5 ↔ cable pin 5, listen wire ↔ cable pin 2. Listened on **both** controller transmit
candidates and got **zero bytes** in every test:
- **TXD1** (controller pin ~3 per label) — silent at 9600/19200/38400/57600/115200 (passive) and
  again during heavy button activity (arrows/Enter/page/**jog Z**).
- **TXD2** — same, silent at all bauds during button activity.

Interpretation: a wrong *baud* would produce garbage bytes, not silence; **zero bytes on both
channels = no signal present**. Most likely the HMI/RS232 port is **input-only** — it accepts key
codes from an external pendant (M3K) but does not transmit status/errors outward. This matches the
skill's "lottery ticket / probably silent" prediction.

Residual uncertainty (can't rule out without a meter): a bad GND/contact or a label-read off by a
pin could also cause silence. A 1-minute multimeter check would confirm definitively — a real TXD
pin idles at **negative** voltage even when not sending; an input/unused pin sits near 0V. If a meter
becomes available, find the negative pin and re-test there before fully closing this out.

**Conclusion: serial is not the path. Use the Ethernet route for error readback.**

## Ethernet route — setup (from official DDCS V4.1 manual, 2026-06-05)
Controller uses a **static IP** (NOT DHCP) and ships on the **192.168.2.x** range by default, so it's
invisible on Fred's **10.0.0.x** router network until reconfigured. Key parameters (manual §3.4.2):
- **#325 – disable network function** → must be turned **OFF** to enable networking. _(This was the
  cause of "no link light" — network was disabled in firmware.)_
- **#327 – Local IP address** (controller's own IP) → set to **10.0.0.50** (verified free on the LAN).
- **#330 – Shared host IP address** (the PC) → set to **10.0.0.34** (PC's wired Ethernet IP).

PC network facts: PC wired Ethernet = **10.0.0.34**, Wi-Fi = 10.0.0.30, router/subnet = 10.0.0.0/24.
Live hosts seen: .1(router) .29 .30 .34 .116 .118 .201 .202 .203 (.50 is free).

After setting params + reboot: expect router link light. Controller share = **`\\10.0.0.50\cncdisk`**.
PC needs **SMB 1.0/CIFS client** enabled (Windows ships it off) — enable via Optional Features / DISM.
Other useful manual bits: `#313` Shift-key mode; controller can also mount a PC folder named **`share`**
(Everyone, Read/Write) as its "Net Disk".

## Open decision
- [x] ~~Path B — Serial probe~~ → **port appears receive-only, abandoned** (see result above).
- [ ] **Path A — Ethernet route** (in progress): enable #325, set #327=10.0.0.50, #330=10.0.0.34 on the
  controller; enable SMB1 on PC; reach `\\10.0.0.50\cncdisk`; then add `error.nc` flag-file for error
  readback. _Status: parameters identified, awaiting controller config + link light._
