# DDCS **Expert** (M350) — Build / Setup Guide

**Use THIS at the studio (Expert), not the V4.1 guide.** The Expert differs from the V4.1 in important
ways — don't copy V4.1 steps blindly. Sources: official DDCS-Expert Manual V1 (Part1/Part2) +
`assets/Modbus_RS232_DDCSE/` (Russian community Modbus docs). Items marked **[VERIFY ON MACHINE]**
because param numbers shift between firmware versions.

---

## ⚠️ Key differences from the V4.1
| Thing | V4.1 (home) | Expert (studio) |
|---|---|---|
| **Serial** | no Modbus in firmware | **Modbus supported** — the real readback/control channel |
| **Network direction** | controller *exposes* CNCDISK/SYSDISK; PC reads them | **likely BOTH** — exposes its own disk (V4.1-style, PC reads it) **and** mounts a PC-hosted `share` as "Net Disk". Manual only documents the Net Disk direction, but it's a Linux/Samba box so the V4.1 read path should also work. |
| **Network params** | `#325` enable, `#327` IP… | `#284 "Network Boot Mode" → manu-IP`, then System-Info IP screen |
| **Default IPs** | 192.168.2.x | controller `192.168.0.99`, host `192.168.0.100` |
| **Passwords** | Super Admin 888888 | Operator **666666**, Admin **777777**, Super Admin **888888** |

**Both directions exist** (confirmed on V4.1: it shows a **Local disk** AND a **Net Disk**). So on the
Expert you'll likely have all of these readback/transfer options:
- **PC reads the controller's disk** (V4.1-style: `\\<expert-ip>\...` — read `uservar`/`error.nc`). Test
  the V4.1 SMB recipe against the Expert's IP.
- **Controller reads/writes the PC's `share` folder** ("Net Disk") — good for the controller pushing a
  status file the PC polls locally (no SMB-client setup on the PC).
- **Serial Modbus** — the richest channel for live status/error + control.
Pick whichever is least friction; they're not mutually exclusive.

---

## Part A — Serial / Modbus (primary readback + control channel)
The Expert RS232 is **MAX3232, ±6V true RS-232** → the **SABRENT FTDI cable is correct**. From the
Russian M350 docs:
- **Data is on port 2** (TXD2/RXD2). **Port 1 (TXD1/RXD1) = M3K keyboard** (reserved).
- Format **8N1**, no parity. Controller is Modbus **MASTER** by default.
- Macros (run from G-code): `MSETDATA[X1,X2,X3,X4,X5,X6]` writes controller vars #50–#499 → slave
  registers; `MGETDATA[...]` reads slave regs → #50–#499. X1=start var, X2=slave#, X3=start addr,
  X4=byte length (Modbus reg = 2 bytes), X5=function/mode, X6=var for exception code.

**Setup on the controller:**
1. Enable Modbus RTU — **[VERIFY ON MACHINE]** the Russian doc says `#279`, but the official Expert
   manual lists `#279` as "Barcode file location," so the number differs by firmware. On the Param
   page (F3), **search/browse for the "Modbus RTU" parameter** and enable it.
2. Set the **port-2 serial baud** — params **`#266` / `#267`** are the serial baud rates
   (B2400/B4800/B9600/B19200/B115200). Confirm which one is port 2 on your firmware. **[VERIFY]**
3. **Reboot** the controller (serial/network params apply only after restart).

**Setup on the PC:** run a **Modbus RTU SLAVE** (the controller is master and polls/writes the PC).
Use the bundled **Termite** (`assets/Modbus_RS232_DDCSE/Termite_1.0.0.6/`, has a Modbus scanner) or
a `pymodbus` slave script. The controller's `MSETDATA` pushes status vars (#200+, incl. error code)
into the PC slave's registers → that's your readback. `MGETDATA` lets the controller pull commands
from the PC.

**Wiring — exact pin map (CONFIRMED via manual §4.7 / `Распиновка разъёма.pdf`).**
Controller connector = **DB-9 female**. Full pinout:
`1=5V  2=RXD1  3=TXD1  4=NC  5=GND  6=5V  7=RXD2  8=TXD2  9=GND`.

Modbus uses **port 2**. Connect **3 wires**, SABRENT cable pin → controller pin:

| SABRENT cable pin | → | Controller pin |
|---|---|---|
| **3** (TX, PC out) | → | **7** (RXD2) |
| **2** (RX, PC in) | → | **8** (TXD2) |
| **5** (GND) | → | **9** (GND) |

Data crosses over (PC TX → controller RX; controller TX → PC RX); grounds tied. Use a DB-9 breakout to
land just these 3 pins. (Find the PC COM port in Device Manager → Ports.)

> **M3K keypad** (separate from Modbus) is on **port 1** (RXD1=pin 2, TXD1=pin 3), enabled by
> **`#268 = M3K`** at **115200** (`#266`/`#267`). Its byte-level protocol is kernel-level (not in the
> app binaries) — see `FINDINGS.md`.

---

## Part B — Network file share (for pushing G-code to the controller)
On the Expert the **PC hosts the share** and the controller reads it as "Net Disk."

**On the PC (host):**
1. `Settings → Network & Internet → Network Connections` → adapter → Properties →
   **IPv4 → set a static IP** on the controller's subnet, e.g. `192.168.0.100`, mask `255.255.255.0`.
2. **Turn off** Windows Firewall (Settings → Update & Security → Windows Security → Firewall &
   network protection) — at least for the active network.
3. Network & Sharing Center → advanced sharing → **turn on network discovery** + **file & printer
   sharing**.
4. Create a folder named **`share`** → right-click → Properties → **Sharing → Share → add "Everyone"
   → permission Read/Write → Share.**

**On the controller (Expert):**
1. Param page (F3) → **`#284 "Network Boot Mode"` → `manu-IP`** (enter Admin password `777777`).
2. Main page → **F6 System Info → F4 "Set IP Addr"**:
   - **Cable IP Addr** = controller IP, e.g. `192.168.0.99`
   - **Host IP address** = the PC's IP, e.g. `192.168.0.100`
3. **Restart the controller** (mandatory). Re-open System Info to confirm the IP took.
4. Program page → **Switch disks (F1) → Net Disk** → you should see the files in the PC's `share`
   folder. Copy G-code Local↔Net Disk from here. (Note: U-disk and Net Disk can't be active at once.)

---

## Error-readback options on the Expert (ranked)
1. **Serial Modbus (best):** a dispatcher/`sysstart` macro periodically runs `MSETDATA` to push the
   alarm-code/status vars to the PC Modbus slave. Real protocol, bidirectional. **[VERIFY which system
   var holds the live alarm code.]**
2. **Net Disk flag file:** have `error.nc` write a status value to a file in the controller's reach
   that lands in the PC's `share` folder, and poll it on the PC. **[VERIFY a macro can write to Net
   Disk.]**

---

## Reference / things to confirm on the actual Expert
- Passwords: Operator **666666**, Admin **777777**, Super Admin **888888**.
- Default IPs: controller `192.168.0.99`, host `192.168.0.100` (Expert supports **manual IP only**).
- Serial: MAX3232 ±6V, port 2 = data, port 1 = M3K keyboard, 8N1.
- **[VERIFY]** exact param numbers for: Modbus-RTU enable, port-2 baud — browse the param list on the
  machine (search by name), since they differ from both the V4.1 and the doc versions.
- Both disk directions exist (V4.1 shows **Local disk + Net Disk**); the Expert very likely matches.
  Test the V4.1 SMB read recipe against the Expert's IP to confirm direct `uservar`/`error.nc` reads.
- Full Modbus macro reference + register tables: `assets/Modbus_RS232_DDCSE/M350 modbus manual RU.docx`.
