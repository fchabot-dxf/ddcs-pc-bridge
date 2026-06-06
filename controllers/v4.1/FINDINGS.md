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
- **`error.nc` on a runtime alarm (`#3000`)** — `[TO TEST]` (test file `FAULT_TESTB2.nc` armed on
  CNCDISK; `error.nc` currently = `#200 = 8888`, pristine empty backup in `assets/error.nc.bak`).

### Detecting syntax errors over Ethernet — RESULTS (tested 2026-06-06)
1. **Completion sentinel** `[CONFIRMED]` — write a start-marker near the top and a completion-sentinel
   as the *last* line. A syntax error halts execution partway, so the sentinel never gets written.
   PC reads uservar: start-marker set **+** sentinel absent = "started but didn't finish" = **error
   caught**. Proven with `SENTINEL_ERR.nc` (ZZZZ on line 5): slot 101 = 7779 (started), slot 103 = 0
   (sentinel never reached), `.env` idx 148 = 0 (didn't complete). Reliable. Add intermediate
   checkpoint vars to localize roughly *where* it died.
2. **Controller run-state files (SYSDISK), written on every run:**
   - `.file` (332 B, text) = path of the last-loaded file (e.g. `/local/SENTINEL_ERR.nc`). `[CONFIRMED]`
   - `.<name>.nc.env` (888 B) = modal/run state, int32 LE. Confirmed fields: idx 21 = file size,
     idx 23 = run timestamp (Unix), **idx 148 = completion flag — 0 = aborted/errored, 1 = finished
     clean** (0 on both error runs, 1 on a clean run; `[HYPOTHESIS, n=1 clean]`). This is a
     controller-native "did it finish" signal needing **no** sentinel injection.
   - **idx 149 is NOT the error line** `[REFUTED]` — it read **4 for an error on line 4 (FAULT_TESTB)
     and also 4 for an error on line 5 (SENTINEL_ERR)**, so the first sample's "matches l4" was
     coincidence. What idx 149 actually encodes is unknown `[TO TEST]`.
   - `.<name>.nc.pos` (60 B) = axis positions. Not needed for error detection.

**Bottom line:** syntax errors **are** detectable over Ethernet — use the **completion sentinel**
(reliable) backed by the **`.env` idx 148 completion flag** and **`.file`** (which program ran).
The exact error *line* is not yet available in software (idx 149 refuted; on-screen the controller
*does* show "unrecognized file format: l<N>", so the info exists — just not located in a file yet).

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
- [x] ~~Run `SENTINEL_ERR.nc`~~ → **completion sentinel CONFIRMED** (2026-06-06); idx 149 ≠ error line.
- [ ] Confirm `.env` idx 148 = 1 on a **clean** run (n=1 so far) → lock it as the completion flag.
- [ ] Figure out what `.env` idx 149 actually encodes (read 4 for both line-4 and line-5 errors).
- [ ] Run `FAULT_TESTB2.nc` (`#3000` alarm) → does `error.nc` fire on a real alarm? (slot 100 → 8888)
- [ ] Find the system var holding the live **alarm code** (so a hook can log *which* error).
- [ ] Recover M3K serial protocol from `ddcsv4.out` (skill experiment B1).
- [ ] Restore pristine `error.nc` from `assets/error.nc.bak`; clean test files off CNCDISK.
