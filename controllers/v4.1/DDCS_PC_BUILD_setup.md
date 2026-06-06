# DDCS ↔ PC — Build / Setup Guide

**Purpose:** get a *fresh* Windows PC (e.g. the studio laptop) talking to the DDCS V4.1 — file
access over Ethernet, and optionally the serial rig. Everything here is per-machine, so redo it all
on each new PC. Follow top to bottom.

**Fill-in values (write yours here as you go):**
- Laptop IP / subnet: `__________`  (from Step 2)
- DDCS IP: `__________`  (default from our setup: 10.0.0.50)
- USB-serial COM port: `COM___`  (from Step 1)

---

## What you need
- USB-to-serial adapter (the **SABRENT FTDI DB-9**, true RS-232) — only for the serial rig.
- An Ethernet cable from the DDCS to the **same router/switch** as the PC.
- Admin rights on the PC (for the one-time SMB steps).

---

## Step 1 — Serial cable: find its COM port  *(skip if not using serial yet)*
1. Plug the USB end into the PC.
2. Open **Device Manager → Ports (COM & LPT)**. Note the **"USB Serial Port (COMx)"** number.
   - PowerShell alternative:
     ```powershell
     Get-CimInstance Win32_PnPEntity | ? { $_.Name -match 'COM\d+' } | Select Name,Manufacturer
     ```
3. Write the COM number in the fill-in box above. (On the home PC it was COM4 — it WILL differ here.)

---

## Step 2 — Network: put the PC and DDCS on the same subnet
The DDCS uses a **static IP** (no DHCP), so it must be on the same subnet as the studio network.
1. Find the laptop's IP + subnet:
   ```powershell
   ipconfig
   ```
   Look at the active adapter's **IPv4 Address** (e.g. `192.168.1.50`) and **Default Gateway**
   (e.g. `192.168.1.1`). Note them above.
2. Pick a **free** IP on that same subnet for the DDCS (same first 3 numbers, different last number,
   not already used). Quick free-IP check after a ping sweep:
   ```powershell
   1..254 | % { (New-Object Net.NetworkInformation.Ping).SendPingAsync("192.168.1.$_",300) } | Out-Null
   arp -a   # shows which .x are taken
   ```
3. On the **DDCS** (Parameters page — log in as **Super Administrator**, password **888888**), set:
   - `#325` Disable network functionality → **No** (network ON)
   - `#327` Local IP → your chosen DDCS IP (e.g. `192.168.1.60`)
   - `#328` Net mask → `255.255.255.0`
   - `#329` Router IP → the laptop's gateway (e.g. `192.168.1.1`)
   - `#330` Shared host IP → the laptop's IPv4 (e.g. `192.168.1.50`)
   - **Reboot the controller** (network params only apply after a power-cycle).
   - Note: if the on-screen edit won't stick, edit the `setting` file instead (see Reference) —
     but network must already be up for that, so first time, persist it on the panel.
4. Confirm link: the router port + DDCS jack should show a link light; then:
   ```powershell
   Test-Connection <DDCS-IP> -Count 2
   ```

---

## Step 3 — One-time Windows SMB setup (admin + reboot)
The DDCS is an old **SMB1 + guest + NTLM** device; Windows blocks all three by default.
1. Open **PowerShell as Administrator** (Start → type *powershell* → right-click → Run as administrator).
2. Enable the SMB1 client (**parent feature first**, then client):
   ```powershell
   Enable-WindowsOptionalFeature -Online -FeatureName SMB1Protocol -NoRestart
   Enable-WindowsOptionalFeature -Online -FeatureName SMB1Protocol-Client -NoRestart
   ```
3. Allow guest logons + NTLM for SMB:
   ```powershell
   Set-SmbClientConfiguration -EnableInsecureGuestLogons $true -Force
   Set-SmbClientConfiguration -BlockNTLM $false -Force
   ```
4. **Restart the PC** (required for SMB1 to load).

---

## Step 4 — Connect to the controller's shares
**Establish a guest session FIRST** — direct access fails without it:
```powershell
net use \\<DDCS-IP>\IPC$ /user:guest ""
net view \\<DDCS-IP>            # should list CNCDISK and SYSDISK
```
Then open in Explorer's address bar or PowerShell:
- `\\<DDCS-IP>\cncdisk`  → work disk (your G-code files)
- `\\<DDCS-IP>\sysdisk`  → system folder (`error.nc`, `setting`, `uservar`, `ddcsv4.out`, macros)

---

## Step 5 — Verify read + write
```powershell
# read
Get-ChildItem \\<DDCS-IP>\sysdisk | Select Name,Length | Format-Table
# write + cleanup (safe, on the work disk)
"test" | Out-File \\<DDCS-IP>\cncdisk\pc_write_test.txt -Encoding ascii
Get-Content \\<DDCS-IP>\cncdisk\pc_write_test.txt
Remove-Item \\<DDCS-IP>\cncdisk\pc_write_test.txt
```
If all three work, the PC↔controller file channel is ready.

---

## Reference / cheat-sheet
**Controller login:** Super Administrator, password **888888**.

**Key params:** `#325` network enable, `#327` local IP, `#328` mask, `#329` gateway, `#330` host IP,
`#326` obtain-IP-auto (leave **No** = static). Changes need a **reboot**.

**`setting` file** (`\\<DDCS-IP>\sysdisk\setting`): 1500 little-endian doubles, indexed by param #.
IPs stored as raw octet bytes at #327–330. Editing this file over SMB is an alternative to the panel.

**`uservar` file** (`\\<DDCS-IP>\sysdisk\uservar`): 400 doubles; **slot = (variable# − 100)**, range
#100–#499. This is how the PC reads controller variables (e.g. an error flag set by `error.nc`).

**Error readback:** on V4.1, `error.nc` does **NOT** fire on software/syntax errors (it's a system-alarm
hook). Detect a bad job instead via the **completion-sentinel** in the running G-code, read from
`uservar` over SMB. See [`FINDINGS.md`](FINDINGS.md) (Error / fault behavior).

**Serial:** Modbus is M350-only (V4.1 has none). On V4.1, port 1 = M3K keyboard, but its protocol is
**kernel-level** — blind serial triggering doesn't work. See [`FINDINGS.md`](FINDINGS.md) (Serial +
Firmware internals); early probe log archived at [`../../archive/DDCS_RS232_probe_notes.md`](../../archive/DDCS_RS232_probe_notes.md).

## Troubleshooting
- `net view` → **Access denied / error 5**: you skipped the guest `IPC$` session in Step 4.
- **error 1937 / NTLM disabled**: redo Step 3 #3 (`BlockNTLM $false`).
- **"share does not exist"**: guest session not established, or wrong share name (it's `cncdisk` /
  `sysdisk`).
- **Can't ping the DDCS**: wrong subnet (Step 2) or it needs a reboot after the IP change, or no link
  light (bad cable / router port).
- **SMB1 enable error "parent features disabled"**: enable `SMB1Protocol` before `SMB1Protocol-Client`.
- **Param won't save on panel**: log in as Super Admin (888888); if still stubborn, edit `setting`
  over SMB instead.
