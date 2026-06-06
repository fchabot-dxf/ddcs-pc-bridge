# DDCS Homebrew — Master Experiment Plan

The full roadmap for building an unofficial PC/AI control API over the DDCS. Organized into
**tracks**. Track A and B need **no hardware** and can be done tonight-or-whenever. C onward needs a
cheap ESP32. Each experiment lists **Needs · Goal · Method · Proves · RESULT**.

**Hardware legend:** 🟢 nothing extra · 🔵 ESP32 (~$6) · 🟣 M3K or capture card.
**Primary motivation:** see whether a loaded G-code **errored, and which error** — Track A2/A2b/B4.
Live motor position is *not* wanted (Track D1 only if that ever changes).

```
A. Software over Ethernet      🟢  bench unit + cable + PC        ← start here
B. Desk research / firmware     🟢  no machine needed (my side)   ← parallel
C. Control bridge               🔵  ESP32
D. Sense / eyes                 🔵🟣 optional
E. Integration & autonomy       🔵  ties it together
```

---

# TRACK A — Software over Ethernet (no hardware) 🟢

Rig: spare DDCS V4.1 · Ethernet cable · your PC. No motors/switches needed.
First confirm the unit boots to **READY** with nothing wired; if it's stuck in RESET, disable the
E-stop / hard-limit params.

## A0 — Reach the controller's files (prerequisite)
**Needs:** 🟢 · **Goal:** see the DDCS internal files from Windows.
**Method:**
1. On the DDCS network/system page, note its IP (e.g. `192.168.1.50`); link it to your router/switch.
2. Windows: Start → "Turn Windows features on or off" → tick **SMB 1.0/CIFS Client** → reboot if asked.
3. File Explorer address bar:
   ```
   \\192.168.1.50
   ```
   (`\\` = a network computer, not a disk folder. Use your unit's real IP.)
**Proves:** you can read/write the share (`error.nc`, `pause.nc`, `mdi.nc`, G-code files…).
**Fail modes:** "cannot access" → SMB1 client off, wrong IP, firewall, or sharing disabled on the unit.
**RESULT (A0):** see files? ___  Controller IP: ___

## A1 — File-reload test
**Needs:** 🟢 · **Goal:** does overwriting a program over the network + Start run the NEW code?
**Method:** save `testreload.nc` on the share:
```
#1505 = -5000 (VERSION A IS RUNNING)
M30
```
Panel: File page → select it → Start → see "VERSION A". Now from the PC edit the file to say
"VERSION B", save. Panel: press **Start again without re-selecting**.
**Proves:** B shown → controller re-reads from disk → **remote job-swap works** (overwrite + later
external-Start). A shown → it caches → need a panel/key "select" after each upload.
**RESULT (A1):** version after PC edit + Start: ___

## A2 — Error readback via `error.nc`  ⭐ (the important one)
**Needs:** 🟢 · **Goal:** when it faults, can it leave a flag the PC reads over Ethernet?
**Method:** PC edits `error.nc` on the share to:
```
#1577 = 8888
#1505 = -5000 (ERROR HOOK FIRED)
```
Note the share's file timestamps. Trip a fault on the panel via MDI (e.g. `G555` or obvious junk).
**Proves:**
1. "ERROR HOOK FIRED" dialog → the hook runs on fault. ✅
2. A file's timestamp changes and contains `8888` → that's the persistent-var store, **readable over
   Ethernet** = your software error channel. ✅ (If not, power-cycle and recheck — vars may flush on
   power-off.)
**RESULT (A2):** dialog? ___  file changed: ___  has 8888? ___

## A2b — Which variable holds the error CODE
**Needs:** 🟢 (+ B4 candidates) · **Goal:** report *which* error, not just that one fired.
**Method:** `error.nc` copies the suspected alarm-code system variable into a persistent var and
displays it; trip several different faults, see which value tracks the error. Candidate variable
numbers come from B4.
**Proves:** identifies the alarm-code variable → full "what error" over Ethernet.
**RESULT (A2b):** alarm-code variable = ___

## A3 — Port scan (hidden software shell?)
**Needs:** 🟢 · **Goal:** find a telnet/FTP/web service on the embedded-Linux box.
**Method:** PowerShell (Start → "PowerShell" → blue icon):
```
Test-NetConnection -ComputerName 192.168.1.50 -Port 23
```
(`Test-NetConnection` = built-in port checker; 23=telnet. Repeat for **21** FTP, **80** & **8080** web.)
**Proves:** any `TcpTestSucceeded : True` = a live service → possible shell into `/proc`/shared memory
(a cleaner channel than file polling).
**RESULT (A3):** open ports: ___

## A4 — Live-state file poll (LOW priority — position)
**Needs:** 🟢 · **Goal:** does any file update live with position while running?
**Method:** mount share; in a loop, watch all files' size/timestamp/contents while you jog from the
panel. (Watch `coordinate` and anything that changes.)
**Proves:** a live file → software DRO with no tap. Expected to **fail** (NAND wear → ~15%). Only
matters if you ever want position; skip otherwise.
**RESULT (A4):** any file tracks position? ___

## A5 — MDI-over-network execution
**Needs:** 🟢 · **Goal:** can the PC inject a single G-code line by writing `mdiblock`/`mdi.nc` on the
share, then triggering MDI?
**Method:** overwrite `mdiblock` (or `mdi.nc`) over SMB with a known line that shows a `#1505` dialog;
trigger MDI on the panel; see if it runs your injected content. Then test whether MDI can be triggered
*without* the panel (relates to C — needs an input/key).
**Proves:** a second remote-command path independent of the file-run flow.
**RESULT (A5):** injected MDI ran? ___  trigger needs panel? ___

## A6 — Macro-hook survey
**Needs:** 🟢 · **Goal:** map every event hook and whether it can signal the outside world.
**Method:** for each of `error.nc`, `pause.nc` (`M119`), `ext_button.nc` (`M#1996`), `key-1..7.nc`,
`extnc0/1/2.nc`: put a `#1505` marker + persistent-var write inside, trigger the event, log what fires
and whether it lands in a share file or could raise an output.
**Proves:** the full catalog of "controller events you can hook" — the backbone of the homebrew API.
**RESULT (A6):** table of hook → fires-on → can-signal.

## A7 — Virtual button `#2037` works ⭐ (the new primary control)
**Needs:** 🟢 · **Goal:** confirm a running macro can press panel buttons via `#2037`.
**Method:** run a tiny file on the panel:
```
#2037 = 65536 + [1373 - 1000]   ; press Monitor page
G4 P1
#2037 = 65536 + [1348 - 1000]   ; press MDI page
M30
```
Watch the screen switch pages.
**Proves:** software button injection works → navigation/file-select/start all become software (no M3K,
no ESP32). Formula: `#2037 = 65536 + [KeyValue - 1000]`; codes in
`Virtual_button_function_codes_COMPLETE.xlsx`. Add `G4 P1` between presses.
**RESULT (A7):** pages switched? ___

## A8 — MDI auto-execute test ⭐ (does the trigger problem vanish?)
**Needs:** 🟢 · **Goal:** can the PC trigger execution over Ethernet alone — no panel, no hardware?
**Method:** from the PC, overwrite `mdiblock` on the share with a self-announcing line
(`#1505 = -5000 (MDI RAN FROM PC)`). Then check, in order:
(a) does it run on its own? (b) does it run after some refresh/state change? (c) can a hook
(`sysstart.nc`) press the MDI-run virtual button (`#2037`) to fire it?
**Proves:** if any of these execute `mdiblock` without a manual press → **fully hardware-free remote
command channel.** This is the single most important unknown in the project.
**RESULT (A8):** mdiblock executed remotely? how? ___

## A9 — Dispatcher bootstrap + survival (the one wall)
**Needs:** 🟢 · **Goal:** beat the one-program-at-a-time rule without hardware.
**Method:** put a polling loop in `sysstart.nc` (auto-runs at boot) that reads a command variable and
fires the matching `#2037` button; test: (a) does sysstart keep running as a loop? (b) when it presses
Start for a job, the job replaces it — does the job's `M30`/chaining relaunch the dispatcher? (c) can
the PC feed commands by writing the variable's backing file over SMB?
**Proves:** whether a self-sustaining software dispatcher is possible. **Yes → zero hardware forever.
No → you need exactly one physical Start trigger** (manual button or $6 ESP32), nothing else.
**RESULT (A9):** dispatcher survives? bootstrap path: ___

---

# TRACK B — Desk research / firmware mining (no machine) 🟢

Done from the firmware backup already in `DDCS-Expert-skill/ddcs-expert/references/firmware-backup-*`.
I can run these without you touching the bench.

## B1 — Recover M3K serial key→byte codes from firmware
**Goal:** the keypad protocol (baud, framing, key→byte map) **without owning an M3K**.
**Method:** grep the firmware serial/keyboard handler + the `msg1` key-label table (`CONT/STEP/ZERO/
HOME/PROBE/MIDDLE/AUTO/MDI…`) for the code mapping; cross-ref the MPG/serial port pinout.
**Proves:** lets the ESP32 emulate the M3K (Track C2) with no purchase.
**RESULT (B1):** codes found? ___

## B2 — Mine factory `.nc` as ground truth
**Goal:** correct our hand-written rules using the controller's OWN code (non-circular).
**Method:** read `M3/M5/T/probe/gotozero/abs*/fnd*` and any `slib`-style subroutines; note where
behavior differs from our notes. Factory `.nc` wins every disagreement.
**Proves:** hardens the `ddcs-expert` skill against our own blind spots.
**RESULT (B2):** discrepancies logged.

## B3 — `motiondev.ko` disassembly feasibility (true-emulator path)
**Goal:** assess whether the compiled motion driver can be disassembled to model real motion behavior.
**Method:** identify arch/ABI of the `.ko`; scope the effort. Likely **high-effort, low-priority** —
documented here so the option isn't forgotten.
**Proves:** whether a *faithful* (non-circular) emulator is ever realistic.
**RESULT (B3):** verdict + effort estimate.

## B4 — Alarm-code variable identification (feeds A2b)
**Goal:** candidate system variables that hold the last error/alarm code.
**Method:** mine `DDCS_Variables_mapping_2025-01-04.xlsx` + `community-discovered-variables.md` for
status/alarm variables; produce a short candidate list for A2b to confirm at the bench.
**RESULT (B4):** candidates = ___

---

# TRACK C — Control bridge 🔵 (needs ESP32 ~$6)

The ESP32 is a translator: PC tells it what to do (USB or WiFi); it speaks to the DDCS.

## C1 — Run control via External inputs
**Needs:** 🔵 ESP32 + 3× PC817 optocouplers + resistors.
**Goal:** PC presses Start / Pause / Estop.
**Method:** map IN ports to External Start/Pause/Estop in the IO page. Each: ESP32 GPIO →330Ω→ opto
LED; opto transistor shorts the DDCS input to `COM-` for ~150 ms = a press.
**Proves:** remote start/stop. Combined with A1, a full unattended run-trigger.
**RESULT (C1):** ___

## C2 — Full navigation via M3K serial emulation  ~~[SUPERSEDED by #2037 / A7]~~
> Obsolete: `#2037` virtual buttons do navigation in software. No M3K, no serial emulation. Kept for history.
**Needs:** 🔵 ESP32 + B1 codes (or 🟣 a real M3K to sniff).
**Goal:** every one of the 40 keys from the PC — arrows, Enter, page, **file select**, Start/Stop —
without opening the case.
**Method:** ESP32 UART → DDCS 5V keyboard/serial port; emit the M3K byte for each key on command.
**Proves:** complete remote panel operation. The elegant path.
**RESULT (C2):** keys working: ___

## C3 — Hardware error readback
**Needs:** 🔵 ESP32 + 1× PC817.
**Goal:** instant error signal independent of SMB polling.
**Method:** `error.nc` raises a spare DDCS **output** (A6); ESP32 reads that pin → reports to PC.
**Proves:** low-latency fault detection for the AI loop (can slam Stop).
**RESULT (C3):** ___

## C4 — "Variable-to-button" macro triggers
**Needs:** 🔵 (or just panel) · **Goal:** one trigger runs a whole macro sequence.
**Method:** bind actions to `M#1996` (programmable ext button) and `key-1..7.nc`; ESP32 fires the
trigger. So instead of navigating, the AI calls a pre-written macro ("home", "load+run job X",
"safe-park").
**Proves:** high-level "do this" commands without keystroke-level navigation. (Your variable-input idea.)
**RESULT (C4):** ___

---

# TRACK D — Sense / eyes (optional) 🔵🟣

## D1 — Step/dir position tap (only if position is ever wanted)
**Needs:** 🔵 ESP32 (classic, 8× PCNT) + differential line receivers (AM26C32) or 6N137 optos.
**Goal:** live machine position with no controller cooperation.
**Method:** tap the differential ±5V PUL/DIR pairs at the driver terminals (high-impedance, parallel);
ESP32 **PCNT** counts up/down off the direction pin at up to 1 MHz; convert by pulses-per-unit;
zero at home. Stream to PC.
**Proves:** a DRO mirroring the controller's. ~95% feasible. Currently **not needed** (errors only).
**RESULT (D1):** ___

## D2 — Screen capture + OCR ("eyes")
**Needs:** 🟣 ~$15 HDMI capture card.
**Goal:** the AI literally reads the screen — error **text**, menus, file list.
**Method:** capture the DDCS display; OCR the regions. Also sidesteps file-selection (AI sees the
picker).
**Proves:** full-text errors + visual navigation feedback; the AI's eyes for autonomy.
**RESULT (D2):** ___

---

# TRACK E — Integration & autonomy 🔵

## E1 — PC orchestrator
SMB file push + ESP32 control link + error poll, wrapped as clean functions:
`push_job()`, `start()`, `stop()`, `pause()`, `key()`, `get_error()`. This *is* the homebrew API.

## E2 — Front-end
Wire the API into your existing `ddcs-studio` UI as the operator console / DRO / error panel.

## E3 — AI-in-the-loop
Closed loop: AI generates G-code → `push_job` → `start` → poll `get_error` → abort or continue.
Optionally D2 eyes for error text + menu reading.

## E4 — Safety (MANDATORY before any real machine) ⚠️
- **Independent hardware E-stop** wired around the ESP32 *and* the controller — kills power no matter
  what software thinks.
- **Watchdog** so a hung PC can't leave it running.
- Never run autonomy on the cutting machine without both. Bench V4.1 (no motors) is the safe dev rig.

---

# Dependencies / suggested order

```
A0 ─► A1 ─► A2 ─► A2b ◄─ B4
  └─► A3        A5, A6 (anytime)
B1 ─────────────────────────► C2
A2/A6 ─► C3
(buy ESP32) ─► C1, C3, C4 ─► E1 ─► E2 ─► E3   (E4 gates any real-machine run)
D1/D2 optional, slot in when wanted
```

**Tonight-able with zero hardware:** A0–A6 (bench) and B1–B4 (I can run from the firmware backup).
Everything else waits on a $6 ESP32. The error-detection goal is fully reachable in Track A alone.

## M3K without buying one / invasive fallback
- Preferred: **B1** recovers the codes from firmware → emulate with ESP32 (C2), no purchase.
- If B1 fails and you don't want an M3K: **matrix tap** — open the unit, wire the ESP32 into the 40-key
  matrix via analog switches/opto array → any key. Always works, but invasive (case open, soldering,
  warranty). Last resort.
