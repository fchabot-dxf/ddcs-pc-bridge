# Ghidra target list — `parse.out` (Expert Modbus serial protocol)

**Goal:** extract the Expert's exact Modbus-over-serial implementation (port↔Uart mapping, baud,
parity/stop/data bits, frame format, function codes, CRC, and the var↔register mapping) so a PC-side
Modbus **slave** can talk to it precisely. This is the Expert's documented `MSETDATA`/`MGETDATA`
channel — the real control + readback path.

**Binary:** `…/nand1-1/parse.out` — `ELF 32-bit ARM LE, EABI5, dynamically linked, STRIPPED`.
**Ghidra:** import → language **`ARM:LE:32`** (Cortex-A / ARMv7, i.MX class — confirm from the ELF header)
→ run auto-analysis. Because it's stripped, **anchor on Defined Strings + imported libc calls**
(`open`, `tcgetattr`/`tcsetattr`, `cfsetispeed`/`cfsetospeed`, `read`, `write`, `select`,
`pthread_create`, `ioctl`) — Ghidra resolves the imports through the PLT.

## String anchors → what each unlocks
`Window → Defined Strings`, then follow **Xrefs**:

| String anchor | Leads to | Extract |
|---|---|---|
| `/dev/ttymxc1`, `/dev/ttymxc2`, `/dev/ttySP0/1` | the `open()` call (`OpenSERIAL01`/`02`) | **which device = Uart0 vs Uart1** (docs say data is on port 2) → port↔Uart map |
| `SetupSerial 1` | the termios config fn | the arg to `cfsetispeed/ospeed` = **baud constant** (`B9600`=0x0d, `B19200`=0x0e, `B38400`=0x0f, `B57600`=0x1001, `B115200`=0x1002); `c_cflag` bits = data/parity/stop |
| `Unsupported parity`, `Unsupported stop bits` | branches in `SetupSerial` | confirms the **parity/stop options** the firmware accepts (and the param→termios mapping) |
| `Enter Uart0 modbus communication %s`, `Enter Uart1 Modbus Communication %s` | the per-UART Modbus **thread** (`pthread_create`) | the request-build → `write()` → `read()` → validate loop = the **frame format** |
| `@Data check: uCRC=0x%x, uCRCTmp=0x%x` | the CRC validate site | the **CRC fn** — expect Modbus **CRC-16** (poly `0xA001`, init `0xFFFF`); look for a 256-entry table or the bitwise loop |
| `Uart0/Uart1 modbus parameter address err!` | register-address bounds check | the **var(#50–#499) ↔ Modbus register/slave** mapping + valid ranges |

## Reconstruct & record
1. **Port map:** ttymxcN ↔ Uart0/Uart1 ↔ physical port 1/2 (M3K is port 1; Modbus data is port 2).
2. **Line settings:** baud (from `cfsetispeed`), data/parity/stop (from `c_cflag`) → confirm "8N1".
3. **Frame:** header/addr/function/len/data/CRC layout from the comm thread.
4. **Function codes:** 03 (read holding), 04 (read input), 06 (write single), 16 (write multiple).
5. **CRC:** confirm CRC-16/Modbus.
6. **`MSETDATA[X1..X6]` / `MGETDATA`:** map args (start var, slave#, start addr, byte len, function/mode,
   exception var) to the frame — cross-ref `assets/Modbus_RS232_DDCSE/M350 modbus manual RU.docx`.

**Deliverable:** a table {device→Uart→port, baud, 8N1, function codes, CRC} + the var↔register map →
configure a `pymodbus` slave on the PC to mirror it exactly.

---

## (Separate) Unlocking the M3K keypad protocol — needs the kernel
`parse.out` (like V4.1's `ddcsv4.out`) reads the M3K via `/dev/input/event*`; the serial→keystroke
driver is **kernel-level** and **not** in `nand1-1` (app partition only). To get it:
- **NAND dump** of the boot/kernel partition from the Expert, **or** a **full firmware image** from the
  community forum **bbs.ddcnc.com** (the official ddcnc.com/nvcnc updates are app-layer "Install folder"
  only — they won't contain the kernel), **or**
- **sniff a real M3K** pendant inline (true RS-232; tap TX/GND with the SABRENT into a terminal).
