# V4.1 — Ethernet-only Test Plan (no serial, no extra hardware)

Living checklist of tests doable over the SMB share against the bench V4.1 @ `10.0.0.50`.
Status: ✅ done · 🔄 staged/in-progress · ⬜ to do. Detail/provenance lives in [`FINDINGS.md`](FINDINGS.md).

> Goal hierarchy: (1) read whether a job errored ✅ achieved; (2) trigger execution without the panel
> (the thing that decides whether serial is even needed); (3) full PC→controller command channel.

## ✅ Done
- [x] **A0 — Reach files over SMB** (cncdisk + sysdisk, R/W/delete; guest recipe).
- [x] **uservar decoded** (400×f64, slot = #var−100, #100–#499; flushes even on abnormal stop).
- [x] **error.nc on syntax error → does NOT fire** (loader-level "unrecognized file format").
- [x] **Syntax-error detection via uservar sentinel + checkpoints** — proven clean (slot=9999) *and*
      error (slot=0) cases. The reliable software error signal.
- [x] **Run-state files** — `.file` = last loaded program (useful); `.env` idx 148/149 do NOT track
      status (refuted).
- [x] **Port scan** — only 139/445 (SMB) open; no hidden telnet/SSH/FTP/web service.

## 🔄 Staged / in progress
- [ ] **#3000 alarm → error.nc** (`ALARM_TEST.nc` pushed). Does the fault hook fire on a *real alarm*?
      Read: slot 100 → 8888 = fired; `#202` canary stays 0 = alarm halted. Also note screen (alarm vs
      "unrecognized") to confirm `#3000` is supported on V4.1.

## ⬜ To do — "can we trigger without the panel?" (decides if serial is needed)
- [ ] **#2037 virtual buttons** — does a *running* macro pressing `#2037 = 65536+[KeyValue−1000]`
      switch pages / press Start on V4.1? (V4.1 key codes may differ from the M350 table — start with a
      harmless page switch.) Proves the software navigation/Start primitive.
- [ ] **sysstart.nc auto-run** — confirm `sysstart.nc` runs at boot (drop a marker var, reboot, read it).
- [ ] **sysstart.nc dispatcher loop** — can sysstart sustain a poll loop that reads a PC-written command
      file and fires `#2037`? If yes → **zero-hardware control, serial unnecessary.**
- [ ] **MDI-over-network** — overwrite `mdiblock`/`mdi.nc` over SMB; can it execute without a panel
      press (on its own, after a refresh, or via a hook firing the MDI-run `#2037`)?

## ⬜ To do — command channel & readback depth
- [ ] **PC→controller variable write** — can the PC write a `uservar` slot over SMB and have the
      controller read that value in a macro? (The inbound command path.)
- [ ] **Variable persistence across power cycle** — do PC/macro writes to #100–#499 survive a reboot?
- [ ] **Alarm-code variable hunt** — find which system var holds the last error/alarm code so a hook can
      log *which* error (feeds A2b). Trigger several faults, diff uservar / read candidates.
- [ ] **Macro-hook survey** — which event hooks fire and can leave a flag: `pause.nc` (M119),
      `key-1..7.nc`, `ext_button.nc` (M#1996), `extnc0/1/2.nc`, `error.nc`. Map hook → fires-on → can-signal.

## ⬜ To do — automation linchpins
- [ ] **File-reload / remote job-swap** — overwrite a selected job over SMB, press Start again *without
      re-selecting* → does it run the NEW contents (re-reads disk) or cache the old?
- [ ] **Event file-diff** — snapshot sysdisk before/after various events to find any other status files
      the controller writes (beyond uservar / `.file` / `.env`).

## Housekeeping
- [ ] Restore pristine `error.nc` from `assets/error.nc.bak` when fault testing is finished.
- [ ] Orphaned run-state companions on sysdisk (`.FAULT_TESTB.nc.env`, etc.) can be cleaned anytime.
