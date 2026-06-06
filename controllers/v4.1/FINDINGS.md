# DDCS V4.1 — Confirmed Findings (bench unit)

**Unit:** spare DDCS V4.1, no motors, no switches — the safe sandbox. **On the LAN at `10.0.0.50`.**
**Scope:** facts established on *this* controller. Do not assume they hold on the Expert/M350.

> Tags: `[CONFIRMED]` verified here · `[TO TEST]` open · `[HYPOTHESIS]` unverified guess.

---

## Network / file access
- **SMB file share over Ethernet works, full read/write/delete.** `[CONFIRMED]`
  Shares: `\\10.0.0.50\cncdisk` (work disk, G-code) and `\\10.0.0.50\sysdisk` (system folder).
  Connection recipe (one-time on PC): SMB1 client installed; `EnableInsecureGuestLogons $true`;
  `BlockNTLM $false`; then **establish guest session FIRST** —
  `net use \\10.0.0.50\IPC$ /user:guest ""` — *then* the shares open.
- Controller network params already set: `#325` network ON, `#327`=10.0.0.50, `#328`=255.255.255.0,
  `#329`=10.0.0.1, `#330`=10.0.0.34 (PC). Network param changes need a reboot. `[CONFIRMED]`
- **Port scan (2026-06-06): only `139` + `445` (SMB/NetBIOS) open.** No telnet/SSH/FTP/web/rsync/NFS.
  `[CONFIRMED]` → the SMB share is the *only* network channel; there is no hidden service/shell to use.

## Variable storage (`uservar` on SYSDISK)
- `uservar` = 3200 bytes = **400 little-endian float64**. **slot = (#var − 100)**, covers #100–#499.
  `[CONFIRMED]` (e.g. #200 → slot 100 at byte offset 800). High vars like #1505 are NOT stored here.
- A variable written by a running program **flushes to `uservar` and is immediately readable over
  SMB** — even when the program ends abnormally (proven: a marker write survived a syntax-error stop).
  `[CONFIRMED]`
- `setting` file = 1500×f64, positional by param #; IPs stored as raw octet bytes at #327–330.
  `[CONFIRMED]` (see `assets/setting`).

## Error / fault behavior ⭐ (the core question)
- **`error.nc` does NOT run on a G-code syntax / parse error.** `[CONFIRMED]`
  Test: ran a file with a garbage token `ZZZZ` → controller showed **"unrecognized file format: l4"**
  (a *loader* rejection). Lines before the bad line executed (marker var was set), the bad line
  halted it, but `error.nc` (armed to write `#200=8888`) never fired — slot 100 stayed at baseline.
  **Implication: the `error.nc` hook is useless for catching the syntax errors we care most about.**
- **`error.nc` did NOT fire on `#3000` either.** `[CONFIRMED]` On V4.1 `#3000=1(MSG,...)` is **not an
  alarm** — the screen showed *"macro variable assignment error: L4"* (it tried to assign var #3000).
  Execution halted, slot 100 stayed 22222. So `error.nc` has now failed to fire on **every** software
  error type tested.
- **What `error.nc` is actually for** (official DDCS-Expert install-file description): *"when system
  abnormal working, system will execute this file"* — i.e. a **system-fault / alarm hook, NOT a G-code
  program-error hook.** That explains why it never fired here: a syntax error / `#3000` is a *program*
  error, not a *system alarm*. **`error.nc` was never the right tool for catching syntax errors — on
  either controller.**
- **Does the V4.1 even implement `error.nc`?** Unclear. It does **not** appear in the V4.1 firmware's
  macro-hook string table (only an unrelated `Perror.nc` token), which *hints* V4.1 may not run it —
  but confirming needs a real **hardware alarm** (limit / E-stop / servo), which a motorless bench
  can't produce. `[TO TEST w/ hardware]`
- **`#3000` alarm command is Expert/M350-only** (came from the M350-focused `ddcs-expert` skill). `[CONFIRMED]`
- **`sysstart.nc` is NOT in V4.1 firmware** — DESIGN's "sysstart auto-runs at boot `[CONFIRMED]`" was an
  *Expert* finding. The V4.1's firmware-listed startup/auto hook is likely **`advstart.nc`** ("advanced
  start", 8 B on disk). `[HYPOTHESIS → test next]`
- **Untestable on the bench:** whether `error.nc` or any hook fires on a *hardware* alarm
  (limit / E-stop / servo) — a bare unit with no switches can't produce one. `[TO TEST w/ hardware]`

### Detecting syntax errors over Ethernet — RESULTS (tested 2026-06-06)
1. **Completion sentinel + checkpoints** `[CONFIRMED both directions]` — write a start-marker near the
   top, numbered checkpoint vars between sections, and a completion-sentinel as the *last* line. PC
   reads uservar:
   - **Error run** (`SENTINEL_ERR.nc`, ZZZZ on line 5): slot 101 = 7779 (started), slot 103 = **0**
     (sentinel never reached) → **error caught**.
   - **Clean run** (`CLEAN_RUN.nc`): slot 101 = 7780, checkpoints 110 = 1111 & 111 = 2222 (in order),
     slot 103 = **9999** (sentinel reached) → **clean finish**.
   So `slot103 == 9999` ⇒ completed; anything else ⇒ died, and the highest checkpoint set tells you
   roughly **where**. This is the reliable software error-detector. `.file` (below) tells you *which*
   program the reading belongs to.
2. **Controller run-state files (SYSDISK), written on every run:**
   - `.file` (332 B, text) = path of the last-loaded file (e.g. `/local/CLEAN_RUN.nc`). `[CONFIRMED]` — useful.
   - `.<name>.nc.env` (888 B) = modal/run state, int32 LE. Confirmed: idx 21 = file size, idx 23 =
     run timestamp. **Do NOT use `.env` for status:** idx 148 and idx 149 reflect *program structure*,
     not completion — a **clean** `CLEAN_RUN` and a **failed** `SENTINEL_ERR` both gave idx 148 = 0,
     idx 149 = 4. Both earlier hypotheses (idx 149 = error line; idx 148 = completion flag) are
     `[REFUTED]`. The original diff vs `MAP_PROBE` just reflected a different program.
   - `.<name>.nc.pos` (60 B) = axis positions. Not needed for error detection.

**Bottom line:** syntax errors **are** reliably detectable over Ethernet via the **uservar completion
sentinel + checkpoints** (proven clean *and* error cases), with **`.file`** identifying the program.
The exact error *line* is not available in any file yet (the controller shows "unrecognized file
format: l<N>" only on-screen); checkpoint granularity is the current substitute for localization.

## Variable RAM/file model + PC→controller inbound channel — `uservar` does NOT work
- **Model `[CONFIRMED]`:** the controller holds variables in **RAM** (persistent across runs) and
  flushes **RAM→file at run start *and* end**, but **never reads file→RAM**. So `uservar` is a
  one-way **readback** channel (controller→file→PC, proven) and PC writes to it are ignored.
- **Inbound test (45 s dwell, proper run):** pre-staged `#220` in the file before launch, and wrote a
  second value to the file *during* the dwell. The macro captured `#221 = 0` (at start) and
  `#222 = 0` (after the live write) — it read **RAM (0)** both times, never the file values. `#220`
  kept my file edit only because the macro never *wrote* `#220` (unwritten vars aren't flushed over).
- ⇒ **PC writes to `uservar` are invisible to a running/starting program.** A polling "dispatcher"
  therefore **cannot receive commands over SMB** — a running program is sealed from SMB file changes.
- **Implication:** a *live* inbound PC→controller channel needs **hardware** — the serial **M3K
  keyboard port** (read live by firmware, even mid-run) or the external Start/Pause inputs.
  **This is the concrete, evidence-based reason serial matters on the V4.1.**
- Note: `G4 P<ms>` dwell **works** (visually confirmed ~45 s). An earlier "finished in ~2 s" reading
  was a misread — it was the **stale RAM value flushed to the file at run start**, not completion.

## Triggering & remote job-swap — the autonomy path `[CONFIRMED]` ⭐
- **File-reload works:** overwrite the *already-selected* job file over SMB, then press **Start again
  without re-selecting** → the controller **re-reads the file from disk and runs the NEW contents.**
  Proven: version A set `#230=1001`; PC overwrote the file to version B (`#230=2002`); a second Start
  (no re-select) → slot 130 = **2002**. (Unlike `uservar`, the *program file* IS re-read on Start.)
  Also survives a full **delete + re-transfer** (same name): version C (`#230=3003`) ran on the next
  Start → the selected file is resolved by **path/name at Start**, not a cached handle, so *any* push
  method (overwrite-in-place **or** delete-and-recreate) works.
- ⇒ **The trigger reduces to a dumb "Start" pulse** — no navigation, no file-select, no serial protocol.
- **Autonomy loop (V4.1):**
  1. one-time: select the master job file on the panel once;
  2. PC overwrites that file over Ethernet (SMB) ✅;
  3. pulse the **External Start input** (NPN active-low — a ~$6 relay/optocoupler/ESP32; no protocol,
     no voltage gamble) ← the only hardware needed;
  4. controller re-reads + runs the new job; PC polls the **uservar sentinel** for clean/errored ✅.
- **Serial M3K is NOT required for triggering** — its only edge (panel navigation) is unnecessary once
  file-reload + a Start pulse cover job-swap. Serial → fallback/nice-to-have, not the path. `[TO TEST]`:
  confirm the External Start input fires a run on the bench (IO-page mapping + a contact closure).

## Homing & the Expert `sysstart` equivalent
- The Expert's `sysstart.nc` runs **`M115`** ("execute standard startup homing") + gantry sync
  (`#883=#881`, `#1518=1`). **`M115` does NOT exist on the V4.1** `[CONFIRMED via V4.1 G/M-code manual]`.
- **V4.1 homing commands** (official manual): `M105`=X home, `M106`=Y home, `M107`=Z home, `M108`=A
  home (put on one line to home together); or **`G128 X1 Y1 Z1 A1`** = home all axes at once. Also
  `G28`/`G30` = go to recorded origin via a reference point.
- So the V4.1 translation of the Expert startup routine ≈ `G128 X1Y1Z1A1` (or `M105 M106 M107 M108`)
  + gantry-sync writes — but the gantry-sync **variable numbers** (`#883`/`#881`/`#1518`) must be
  re-verified on the V4.1 (variable maps differ between controllers). `[TO VERIFY]`

## Serial
- **No Modbus in V4.1 firmware** — checked the newest build (`ddcsv4(2025-04-04)`): 0 hits for
  SETDATA/GETDATA/Modbus/MAX323; no serial/baud labels in its param files. `[CONFIRMED]`
  Modbus is an **Expert-only** feature.
- HMI/RS232 port carries **two channels** (TXD1/RXD1, TXD2/RXD2) + 5V pins. **Port 1 = M3K keyboard**
  (input). A listen-only probe on both TX lines was **silent at all bauds** → likely input-only.
  `[CONFIRMED silent]`
- Fred's preferred control path: **Ethernet = data, serial port 1 (M3K) = trigger** — emulate M3K
  keystrokes to press Start/navigate from the PC with no running program. Needs the M3K protocol
  (baud + key→byte map) recovered from `assets/system-backup/current/ddcsv4.out`. `[TO TEST]`

## Assets in this folder
- `assets/firmware/` — V4.1 firmware backup (incl. `ddcsv4.out`, factory `.nc`/`.rc` macros).
- `assets/system-backup/current/` — full live system snapshot (79 files, pristine `error.nc`).
- `assets/uservar-snapshots/` — before/after `uservar` dumps from the Test B sessions.
- `assets/error.nc.bak` — pristine (empty) `error.nc`. **Restore this when done testing.**
- `assets/setting` — controller param file. `assets/ddcs4.1.JPG` — photo of the port/pinout.

## Open actions
- [x] ~~Run `SENTINEL_ERR.nc` + `CLEAN_RUN.nc`~~ → **sentinel + checkpoints CONFIRMED both directions** (2026-06-06).
- [x] ~~`.env` idx 148/149 as status~~ → **REFUTED**: reflect program structure, not completion. Use uservar.
- [ ] Run `FAULT_TESTB2.nc` (`#3000` alarm) → does `error.nc` fire on a real alarm? (slot 100 → 8888)
- [ ] Find the system var holding the live **alarm code** (so a hook can log *which* error).
- [ ] Recover M3K serial protocol from `ddcsv4.out` (skill experiment B1).
- [ ] Restore pristine `error.nc` from `assets/error.nc.bak`; clean test files off CNCDISK.
