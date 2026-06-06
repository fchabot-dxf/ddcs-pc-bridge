# DDCS Homebrew Control API — Design Notes

**Project:** `ddcs-pc-bridge` (a homebrew / reverse-engineered control API for the DDCS)
**Target machine:** DDCS Expert M350 (Ultimate Bee 1010)
**Dev/test bench:** spare **DDCS V4.1**, Ethernet, no motors, no switches (safe sandbox)
**Status:** design + experiment plan. Nothing here is production-validated yet.
**Last updated:** 2026-05-31

> Confidence tags follow the `ddcs-expert` skill convention:
> `[CONFIRMED]` = established · `[TO TEST]` = bench-testable open question · `[HYPOTHESIS]` = best guess, unverified

---

## 1. What this is

The DDCS Expert is a sealed, standalone, offline controller with **no official API** — no
telemetry protocol, no remote-command interface. This project synthesizes an *unofficial* one
by repurposing the interfaces the vendor built for humans and accessories. In driver terms,
we're writing an **unofficial driver / control shim** for the DDCS.

### The goal (what the PC — and eventually an AI — should be able to do)
1. **Push** a G-code program to the controller.
2. **Start / stop / pause** a run.
3. **Navigate** the panel (menus, file select) remotely.
4. **Read whether the program errored, and which error.** ← the original and primary motivation.

### The actual need, restated
> "If I load a G-code I want to see errors." Live motor position is **not** wanted. Only the
> error verdict matters. This sharply changes the difficulty — see §5.

---

## 2. What we established about the DDCS

| # | Finding | Confidence |
|---|---------|------------|
| 1 | No official PC API; no command/telemetry channel. | [CONFIRMED] |
| 2 | Ethernet port = **SMB file share** (SMB1; enable on Windows). Reads/writes files only. | [CONFIRMED] |
| 3 | USB port = flash-drive transfer only. | [CONFIRMED] |
| 4 | No official PC **emulator/simulator** exists. Only an on-device dry-run/sim mode. | [CONFIRMED] |
| 5 | Live position is **not** expected in any flash file (NAND wear → firmware wouldn't write DRO every move). The `coordinate` file is a save/power-off snapshot, not live. | [HYPOTHESIS ~15%] |
| 6 | Controller has discrete status states: `READY / BUSY / RESET / ERROR / ALARM` (from firmware `msg1`). | [CONFIRMED] |
| 7 | `error.nc` is a user-editable macro the controller runs **on fault**. Currently empty. | [CONFIRMED exists] |
| 8 | **M3K external keyboard** connects over a **serial port** (5V, powered by the controller) and natively does menu navigation, file select, and start/stop. | [CONFIRMED] |
| 9 | **External Start / Pause / Estop** inputs exist, are user-mappable in the IO page, and are NPN active-low (trigger by pulling to `COM-`). | [CONFIRMED] |
| 10 | Programmable external button runs a macro via `M#1996`; K1–K7 keys run `key-N.nc` macros. A **variable/macro can be used to drive an action** (Fred's insight). | [CONFIRMED mechanism, mapping TO TEST] |
| 11 | An emulator built from our own reverse-engineered rules is **circular** — it only reflects our model back. Ground truth = the factory `.nc` files, `motiondev.ko`, or the real machine. | [CONFIRMED reasoning] |
| 12 | **`#2037` virtual button** — writing `#2037 = 65536 + [KeyValue - 1000]` from a macro **presses any panel button** (201 codes in `Virtual_button_function_codes_COMPLETE.xlsx`: Start=1328, Enter=1013, arrows, file open/select, page switches, jog, spindle, work-zero…). Official. **Supersedes the M3K serial-emulation idea entirely.** | [CONFIRMED] |
| 13 | **`sysstart.nc` auto-runs at boot** (today it does homing/gantry-sync). One "free" entry point per power-on. | [CONFIRMED] |
| 14 | **The execution constraint (Fred):** `#2037` only fires *while a program is running*, and the controller runs **one program at a time**. So writing a file over Ethernet does NOT execute it — something must press Start. The only no-hands triggers are the auto-hooks: `sysstart.nc` (boot), `error.nc` (fault), `pause.nc`, `key-N.nc`, `ext_button.nc`. | [CONFIRMED constraint] |

### ⭐ Consequence + the one wall
`#2037` + `sysstart.nc` mean navigation, file-select, and start/stop can be driven by writing a
variable from a macro — so the **M3K is obsolete** and the **ESP32 may be unnecessary**. BUT per
finding #14, you can't bootstrap execution from a static file. Solving control **without hardware**
reduces to one question: *can an auto-hook (sysstart) launch a dispatcher that keeps running — or
re-launches itself via macro-chaining — so the PC can feed it commands?* (Experiments A7–A9.) If yes:
zero hardware. If no: one physical Start trigger needed (manual button or the $6 ESP32, nothing more).

---

## 3. Architecture — the homebrew API

> **Revised after the `#2037` discovery.** Primary control is now **software virtual buttons**, not
> the ESP32/M3K. Channel B below is superseded by Channel B′; kept for history.

Each clean PC-side function is backed by a repurposed vendor interface:

```
   PC / AI orchestrator
        │
        ├── push_job(file)  ─────────────►  Ethernet / SMB share   (overwrite job.nc)
        │
        ├── start()/stop()/pause()  ┐
        ├── key(code)  (navigate)   ├────►  ESP32  ──serial──►  DDCS keyboard port
        │                           │        │                  (emulates M3K)
        │                           │        └──optos──►  External Start/Pause/Estop inputs
        │                           ┘                     (fallback / redundancy)
        │
        └── get_error()  ◄───────────────  ESP32 reads output pin raised by error.nc
                          (or)  ◄────────  PC polls a flag file on the SMB share
```

### Channel detail

**A. Program in — Ethernet / SMB.** [CONFIRMED works for files]
PC overwrites a single master `job.nc` on the share.

**B′. Control + navigate — `#2037` virtual buttons (PRIMARY, software).** [CONFIRMED mechanism]
A running macro writes `#2037 = 65536 + [KeyValue - 1000]` to press any of the 201 panel functions
(Start, Enter, arrows, file open/select, page switches, jog, spindle…). No hardware, no keyboard.
The catch (finding #14): it only works inside a running program, and only the auto-hooks run without
a manual Start. So the homebrew API isn't "PC writes a variable" — it's:
  1. PC drops a **command file** on the share (Ethernet).
  2. A **dispatcher macro** (bootstrapped by `sysstart.nc` at boot, kept alive by macro-chaining)
     reads the command and fires the matching `#2037` button.
The unproven link is the dispatcher's survival across the one-program-at-a-time rule → experiments
A7–A9. If it holds, control is 100% software.

**B (obsolete). ESP32 emulating the M3K keyboard.** ~~serial keyboard impersonation~~ — superseded by
B′: `#2037` does navigation natively, so there's no keyboard to emulate and no serial port to tap.
*Remaining hardware fallback, only if A7–A9 fail:* one optocoupler on the **External Start** input so
the PC (via a $6 ESP32) can press Start once to kick the dispatcher. That's the entire residual
hardware need — Start only, no navigation, no M3K, no matrix tap.

**C. Error out — `error.nc` hook.** [design]
Put a line in `error.nc` that raises a spare **output** (ESP32 reads the pin) **and/or** writes a
**persistent variable** (which serializes to a file the PC can poll over SMB). Errors are rare
discrete events, so flash-writing a flag is safe (unlike live position). If a system variable holds
the **alarm code**, `error.nc` can record *which* error, not just that one happened.

**D. Eyes (optional, later) — screen capture.** [design]
A ~$15 HDMI capture card + OCR lets the AI literally read the screen: error text, menus, file list.
This also sidesteps the file-selection problem entirely (the AI can *see* the file picker).

---

### 3.1 The dispatcher pattern — beating the one-program-at-a-time wall

The execution constraint (finding #14) says only one program runs at a time and `#2037` only fires
while something runs. The clean way around it: a long-lived **dispatcher** that never gives up the
executor.

**Key trick: run jobs as subroutines, not loaded files.** A running program can call another `.nc`
with `M98 P<job>` and **regain control when it returns** (`M99`/`M30`). So the dispatcher stays the
executing program the whole time — the job runs *inside* it and hands control back.

```
dispatcher.nc  (launched ONCE — by sysstart.nc at boot, or one ESP32 Start press)
  loop:
    read command  ← PC wrote it over Ethernet (a variable's backing file, or mdiblock)
    if RUN job:   M98 P<job>        ; job runs as subroutine, returns here when done
    if NAV/START: #2037 = 65536+[KeyValue-1000]   ; press any panel button
    if nothing:   G4 P0.2           ; brief wait, poll again
    goto loop
```

Because the dispatcher never dies, it needs **exactly one launch trigger ever** (per power cycle):
- **`sysstart.nc`** auto-runs at boot → if it can sustain the loop, **zero hardware**.
- else **one ESP32 Start press** at boot kicks it off, then software carries the rest.

**Command channel PC→dispatcher** (untested options, see A8/A9): the PC writes a command where the
dispatcher can read it — either a system variable's backing file on the share, or `mdiblock`. The
dispatcher polls it each loop. Errors flow back via `error.nc` writing a flag file the PC polls.

This is what makes "one trigger is enough" true, and it's why the ESP32 — if needed at all — only
ever does a single Start press.

---

## 4. How the PC actually talks to it

The PC never speaks to the DDCS directly for control — it speaks to the **ESP32**, which is the
hardware translator. Two link options PC↔ESP32:

- **USB serial** — simplest, always-connected. PC sends `START\n`, `KEY:DOWN\n`, etc.
- **WiFi (UDP/HTTP)** — no cable, drive it from anywhere on the LAN.

For the file channel, the PC talks to the DDCS **directly over Ethernet/SMB** (mount the share,
copy `job.nc`). So: **files go PC→Ethernet→DDCS; control/keys go PC→ESP32→DDCS; errors come
DDCS→ESP32→PC (or DDCS→SMB file→PC).**

---

## 5. Why "errors only" makes this tractable

Position is continuous + high-rate → no flash file → ~15% software-readable.
An **error is discrete + rare + has a dedicated hook (`error.nc`)** → flash-flag is safe and a
purpose-built trigger already exists. Revised odds for a **software-only error signal**:

| Capability | Odds |
|---|---|
| Software-only "did it error" flag via `error.nc` + persistent var/file | **~60–70%** |
| Getting the actual error **code/text** in software | **~40%** (needs an alarm-code variable) |
| Screen-capture + OCR fallback (full text) | **~95%** |
| Hardware: ESP32 reads an output pin raised by `error.nc` | **~95%** |

---

## 6. Open questions → bench experiments (do these on the V4.1)

Ordered by leverage. All safe: no motors, no switches needed — bare unit on Ethernet.
(Pre-req: confirm the unit boots to **READY** with nothing wired; if stuck in RESET, disable the
E-stop / hard-limit params.)

1. **File-reload test** `[TO TEST]` — load `job.nc`, overwrite it over SMB, hit Start.
   Does it run the **new** contents? If yes → remote job-swap with no panel. *Linchpin for automation.*
2. **`error.nc` → readable flag** `[TO TEST]` — feed a deliberately bad line (a `G10`, or junk),
   trip the fault. Does `error.nc` run? Can it set a **persistent variable** that lands in a file on
   the share? Diff the share before/after the fault.
3. **Alarm-code variable** `[TO TEST]` — find which system variable (if any) holds the last
   error/alarm code, so `error.nc` can log *which* error. *Linchpin for "what error".*
4. **M3K serial protocol** `[TO TEST]` — baud, framing, and the **key→byte map**. Get it by:
   (a) sniffing a real M3K, (b) trial bytes on the bench watching the screen, or (c) digging the
   firmware serial handler + `msg1` key-label table.
5. **Port scan** `[TO TEST]` — embedded Linux box (`motiondev.ko`, `network.conf`). Check for a
   stray telnet/ftp/web service → would be a clean software shell into `/proc` / shared memory.
6. **Live-state file poll** `[TO TEST, low priority]` — only relevant if position is ever wanted.

---

## 7. Hardware (when we build the bridge)

- **ESP32 dev board** (classic ESP32; an **ESP32-S3** if we want native USB-HID tricks too)
- **UART level interface** to the DDCS 5V keyboard/serial port (the M3K-emulation line)
- **4× optocoupler (PC817)** — 3 to drive Start/Pause/Estop inputs (fallback), 1 to read the
  `error.nc` output pin
- resistors, perfboard. ~**$15** total.
- **Optional:** HDMI capture card for the screen-vision "eyes."

### Non-negotiable safety
On the real machine (not the bench), a **hardware E-stop wired independently** of the ESP32 and the
controller is mandatory — a physical button that cuts power no matter what the software thinks —
plus a **watchdog** so a hung PC can't leave it running. Autonomous control of a real spindle/gantry
requires this.

---

## 8. Promotion path (project → skill)

This folder is the **work-in-progress** — unproven ideas live here. As each bench experiment
**confirms** a finding, promote that *verified* fact into the `ddcs-expert` skill (tagged
`[CONFIRMED]`). Don't pour `~60% chance` guesses into the skill — keep it the source of truth.

| Once confirmed | Promote to skill as |
|---|---|
| File-reload behavior (#1) | "Remote job-swap over SMB: works / needs panel select" |
| `error.nc` flag mechanism (#2,#3) | "Error readback pattern + alarm-code variable" |
| M3K key→byte map (#4) | "M3K serial protocol reference table" |
| Port-scan result (#5) | "DDCS network services" |
```
