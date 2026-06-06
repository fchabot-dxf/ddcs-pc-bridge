# Environments / Locations

This project runs in **two physical locations**, each with a different PC, network, and **a
different DDCS controller**. Settings are NOT shared between them — confirm where you are before
acting, and **always identify the controller first** (see below).

> ⚠️ Because the controller, IP, PC, and COM port all differ by location, an action that is correct
> at one site can be wrong at the other. Run `identify-controller.ps1` to be certain which machine
> you're connected to.

## Step 0 — identify the device (do this before anything)
```powershell
.\controllers\identify-controller.ps1 -Ip <controller-ip>
```
It reads the controller's own firmware and prints `V4.1 (bench)` or `EXPERT-M350 (target)`. Trust the
verdict, not the IP.

## Locations

### 🏠 Home — DDCS **V4.1** (bench sandbox)
| | Value | Status |
|---|---|---|
| Controller | DDCS **V4.1**, no motors/switches | ✅ |
| Controller IP | `10.0.0.50` (static) | ✅ |
| Shares | `\\10.0.0.50\cncdisk`, `\\10.0.0.50\sysdisk` | ✅ |
| PC (workstation) | **RENDERRANCHY** (user `danse`) | ✅ |
| PC IP | `10.0.0.34` (Ethernet) · `10.0.0.30` (Wi-Fi) | ✅ |
| Network | router LAN `10.0.0.0/24`, gateway `10.0.0.1` | ✅ |
| Serial | SABRENT FTDI true-RS232 on **COM4** | ✅ (port = M3K keyboard; **no Modbus** on V4.1) |
| File access | SMB1 + guest recipe (see `v4.1/DDCS_PC_BUILD_setup.md`) | ✅ |

### 🏭 Studio — DDCS **Expert (M350)** (real machine)
| | Value | Status |
|---|---|---|
| Controller | DDCS **Expert M350** on Ultimate Bee 1010 — model **DDCSE-5T-standard**, panel "V1.1", **SW Ver 2025-06-19-00**, HW 2021-1213-23, S/N `Digital Dream-0350-3651980d6ca215fb-0000` | `[CONFIRMED on panel 2026-06-06]` |
| Controller IP | `192.168.0.99` (manual-IP only) — **`#284 Network boot mode` was `Close`** (NIC disabled → "Cable IP: Disconnect"); set to `manu-IP` + reboot to bring Ethernet up | `[VERIFY after set]` |
| Host/PC IP | `192.168.0.100` | `[VERIFY]` |
| PC (laptops) | **ASUS A15 TUF** (hostname `____`) and **Panasonic Toughbook** = hostname **`CNC-FAIRY`** | Toughbook `[CONFIRMED 2026-06-06]`, ASUS `[TO FILL]` |
| Network | **direct PC↔controller Ethernet link (no router)** → static IPs both ends; PC may host a `share` ("Net Disk") | `[VERIFY]` |
| CNC-FAIRY wired NIC | adapter name `Ethernet`, MAC `4C-36-4E-94-D4-10`; set static `192.168.0.100/24` here | `[2026-06-06: link DOWN — controller off/cable unseated]` |
| Serial | SABRENT FTDI, COM `____`; **Modbus on port 2**, port 1 = M3K | `[VERIFY — adapter not yet plugged into CNC-FAIRY 2026-06-06]` |
| File access | test V4.1 SMB recipe vs Expert IP, and/or Net Disk | `[TO TEST]` |
| Setup guide | `expert-m350/DDCS_Expert_BUILD_setup.md` | — |

## Per-PC reminder
Every PC step (SMB1 client, guest logon, serial COM number, static IP) is **per-machine** — redo it
on each new PC. The COM port and PC IP **will differ** across all three machines (home RENDERRANCHY,
studio ASUS A15 TUF, studio Panasonic Toughbook).

<!-- Add more locations / details below as needed. -->
