# Shared Architecture (controller-agnostic)

Concepts that apply to **both** the V4.1 and the Expert. Controller-specific detail lives in each
`FINDINGS.md`. Original design/roadmap (historical, superseded): [`archive/DESIGN.md`](../../archive/DESIGN.md), [`archive/EXPERIMENTS.md`](../../archive/EXPERIMENTS.md).

## The homebrew API (what the PC/AI should do)
1. **push_job(file)** — write G-code to the controller's disk (Ethernet/SMB, or Net Disk on Expert).
2. **start / stop / pause** a run.
3. **navigate** the panel remotely.
4. **get_error()** — read whether a program errored, and ideally *which* error. ← primary motivation.

The DDCS has **no official PC API**. We synthesize one by repurposing human/accessory interfaces
(SMB share, serial keyboard/Modbus port, macro event-hooks, virtual buttons).

## The execution wall (applies to both)
- `#2037` virtual buttons only fire **while a program is running**, and the controller runs **one
  program at a time**. So writing a file over Ethernet does **not** execute it — *something must
  press Start.* No-hands triggers are the auto-hooks: `sysstart.nc` (boot), `error.nc` (fault),
  `pause.nc`, `key-N.nc`, `ext_button.nc`.

## The dispatcher pattern (beating the one-program wall, no hardware)
A long-lived **dispatcher** launched once (by `sysstart.nc` at boot) loops: read a command the PC
dropped over the share → run jobs as subroutines (`M98 P<job>`, which returns control via `M99`/`M30`)
or fire `#2037` buttons. Because it never relinquishes the executor, it needs exactly one launch per
power cycle. If self-sustaining → **zero extra hardware**. If not → one physical Start trigger
(manual button or a ~$6 ESP32) is the entire residual hardware need. `[TO TEST on each controller]`

## ✅ Proven minimal autonomy (V4.1) + accepted requirement
**Operator decision:** **one manual button (Start) per power-cycle is acceptable** to bootstrap — full
zero-touch auto-start is *not* required (it's a nice-to-have the Expert's `sysstart` provides for free).

So the dispatcher is **proven and complete with no new hardware**:
1. operator presses **Start once** → launches an **`M47` self-loop** (the program file is re-read from
   disk every cycle — `[CONFIRMED on V4.1]`);
2. PC **injects each job by overwriting the loop file over SMB** (next cycle runs it);
3. PC reads pass/fail via the **`uservar` sentinel** (controller→file→PC).

⇒ **No serial, no relay/optocoupler, no auto-boot hack, no `#2037`** for the V4.1. To harden: atomic
file writes (temp+rename) against torn reads, plus a run-once command protocol. Detail:
[`../v4.1/FINDINGS.md`](../v4.1/FINDINGS.md).

## Error-readback principle
An error is **discrete and rare**, so flash-writing a flag is safe (unlike live position, which is
continuous/high-rate and not expected in any flash file). Mechanisms differ per controller — see the
respective `FINDINGS.md` (V4.1: `uservar` slot + run-state `.env`; Expert: Modbus push / Net Disk flag).

## ⚠️ Safety (MANDATORY before any real-machine autonomy)
- **Independent hardware E-stop**, wired around both the controller and any bridge MCU — cuts power
  regardless of what software thinks.
- **Watchdog** so a hung PC can't leave the machine running.
- Develop and prove everything on the **bench V4.1 (no motors)** first. Never run autonomous control
  on the Expert/Ultimate Bee (real spindle + gantry) without both of the above.
