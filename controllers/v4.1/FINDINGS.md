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

### Detecting syntax errors over Ethernet — two software paths under test
1. **Completion sentinel** `[HYPOTHESIS, partially proven]` — write a start-marker near the top and a
   completion-sentinel as the *last* line. Syntax errors halt execution partway, so the sentinel never
   gets written → PC reads "started but didn't finish" = error. Add intermediate checkpoints to
   localize. (Half-proven: the start-marker flushed on an abnormal stop.) Pending file: `SENTINEL_ERR.nc`.
2. **Controller run-state files** `[HYPOTHESIS]` — when a file runs, the controller writes to SYSDISK:
   - `.file` (332 B, text) = path of last-loaded file, e.g. `/local/FAULT_TESTB.nc`. `[CONFIRMED]`
   - `.<name>.nc.env` (888 B) = modal/run state as int32 LE. Diffing a faulted vs clean env, **int32
     index 149 = 4 matched the on-screen error "l4"** → likely the **stop/error line number**; index
     148 looks like a completion flag (1=ok, 0=didn't finish); idx 21 = file size, idx 23 = run
     timestamp. **One confirming run pending** (run `SENTINEL_ERR.nc`, expect idx 149 = 5).
   - `.<name>.nc.pos` (60 B) = axis positions (doubles). Not needed for error detection.

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
- [ ] Run `SENTINEL_ERR.nc` → confirm sentinel (slot 103 stays 0) **and** `.env` idx 149 = 5.
- [ ] Run `FAULT_TESTB2.nc` (`#3000` alarm) → does `error.nc` fire on a real alarm? (slot 100 → 8888)
- [ ] Find the system var holding the live **alarm code** (so a hook can log *which* error).
- [ ] Recover M3K serial protocol from `ddcsv4.out` (skill experiment B1).
- [ ] Restore pristine `error.nc` from `assets/error.nc.bak`; clean test files off CNCDISK.
