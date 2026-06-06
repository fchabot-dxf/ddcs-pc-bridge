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
  - Args: X1=start var, X2=slave#, X3=start addr, X4=byte length (reg=2 bytes), X5=function/mode,
    X6=var for exception code. Controller pauses ~16 s for a reply. Also `MBYTE2DATA`/`MDATA2BYTE`.
  - Function codes: 01H coils, 02H discrete in, 03H holding, 04H input.
- Scope capture confirmed `MSETDATA[200,1,6,12,15,300]` transmits #200…#203 as Modbus frames. `[CONFIRMED via scope]`
- **Homebrew architecture:** PC runs a **Modbus SLAVE**; the DDCS (master) pushes status vars (#200+,
  incl. error/exception) via `MSETDATA` and reads commands via `MGETDATA`. Bidirectional, documented.

### Params to set (numbers shift by firmware → VERIFY)
- Enable **Modbus RTU**: Russian doc says `#279`, but the official Expert manual lists `#279` as
  "Barcode file location." **Browse the Param page (F3) by name and enable "Modbus RTU".** `[VERIFY ON MACHINE]`
- Port-2 baud: params **`#266`/`#267`** (B2400/B4800/B9600/B19200/B115200). Confirm which is port 2. `[VERIFY]`
- **Reboot** after serial/network param changes. `[CONFIRMED via docs]`

## Network (differs from V4.1)
- Expert supports **manual IP only**. Defaults: controller `192.168.0.99`, host `192.168.0.100`.
- `#284 "Network Boot Mode" → manu-IP`, then System Info (F6) → "Set IP Addr" (F4). Reboot. `[CONFIRMED via docs]`
- **Both disk directions likely exist** (V4.1 shows Local + Net Disk): PC can read the controller's
  disk (V4.1-style — *test the SMB recipe against the Expert IP*) **and** the controller can mount a
  PC-hosted `share` as "Net Disk". `[HYPOTHESIS]` (U-disk and Net Disk can't be active at once.)

## Control
- `#2037` **virtual buttons** press any of 201 panel functions from a running macro
  (`#2037 = 65536 + [KeyValue − 1000]`). `[CONFIRMED]` per the `ddcs-expert` skill
  (`Virtual_button_function_codes_COMPLETE.xlsx`). Subject to the one-program-at-a-time rule.

## Macro hooks — official install-file description `[CONFIRMED via docs]`
From the DDCS-Expert "install file description". These auto-run / are invoked by the firmware:
- **`sysstart.nc`** — *"Boot initialization file — can modify it."* Auto-runs at **boot**. This is the
  Expert's hands-free entry point (the dispatcher-bootstrap candidate). **Absent on V4.1.**
- **`error.nc`** — *"When system abnormal working, system will execute this file."* A **system-fault /
  alarm** hook (NOT a G-code syntax-error hook — see V4.1 findings; program errors won't trigger it).
- **`pause.nc`** (pause), **`key-1.nc`…`key-7.nc`** (K1–K7), **`ext_button.nc`** + **`extnc0/1/2-N.nc`**
  (self-design buttons: release / short-press / long-press), **`probe.nc`**, **`fndX/Y/Z/A/B.nc`** +
  **`fndzero.nc`** (go home), **`gotozero.nc`** (go work zero), **`T.nc`/`ALL_T.nc`** (tool change),
  **`slib-g.nc`/`slib-m.nc`/`slibuser.nc`** (G / M / user libraries), **`absX..B.nc`**.
- `advstart.nc` is **not** in the Expert list (it's a V4.1 file — the "Advanced Start" feature).

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
- [ ] On the actual Expert: confirm SMB read of `uservar`/`error.nc` (V4.1 recipe vs Expert IP).
- [ ] Identify the real param numbers for Modbus-RTU enable + port-2 baud (browse by name).
- [ ] Stand up a PC Modbus slave (Termite or `pymodbus`); confirm `MSETDATA` pushes #200+ to it.
- [ ] Find the system var holding the live alarm code → log *which* error.
