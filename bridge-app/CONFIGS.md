# CONFIGS — vocabulary, deployment configs, shells, distribution, seams

The settled mental model for the bridge (decided across design, 2026-06-07). [`ARCHITECTURE.md`](ARCHITECTURE.md)
is the module-level map; this file is the **deployment + vocabulary + future-seam** reference.

---

## 1. Vocabulary (use these words everywhere)
| Term | Is | Notes |
|---|---|---|
| **Console** | the web app (App 1) — operator-facing UI | one HTML/CSS/JS codebase; submit · queue/tracker · files · admin |
| **Gateway** | fairy (App 2) — the Python service at the machine | holds machine identity, **negotiates the config**, bridges to the controller |
| **Rendezvous** | where Console and Gateway meet | **R2** (cloud) — they never connect directly in cloud mode |
| **API** | the Cloudflare Worker fronting R2 | authed proxy so the browser holds no keys. **Not** "gateway" — that's fairy. |
| **Protocol** | the contract both obey | [`shared/PROTOCOL.md`](shared/PROTOCOL.md) |

One-liner: **Console ↔ Gateway, meeting at the Rendezvous.** The **Gateway is the config authority.**

---

## 2. Deployment configs — two independent axes
Every config is a cell in (UI source × data path). The **client seam** in the console makes them one codebase.

- **Axis A — UI served from:** Cloudflare Pages · or the Gateway (local).
- **Axis B — data path (client):** R2 (cloud) · Direct-to-gateway (LAN) · LocalFolder (same box).

| | data → R2 | data → Gateway (LAN) | data → LocalFolder |
|---|---|---|---|
| **UI from Cloudflare** | **cloud** (from anywhere, phone) | **intermediary** (cloud UI, local data) | — |
| **UI from Gateway** | (odd) | **local-network** (no cloud) | **offline** (one box) |

- **Offline** — Gateway serves the console at `localhost`, LocalFolder rendezvous, **zero internet**. The simplest, most private deployment; also the dev/test path (`--demo`).
- **Cloud** — console on Pages, Gateway polls R2. Submit from anywhere; buffered while the Gateway sleeps.
- **Local-network / Direct** — console (native app) talks to the Gateway over the LAN. Low latency, no cloud.
- **Intermediary** — cloud-hosted UI + data over Ethernet. *Browser can't do this* (HTTPS→LAN-HTTP mixed-content); only a **native app** can. We chose **not** to solve it for the browser (no Tailscale) — use the native app for local data.

---

## 3. Shells (how the one HTML console is delivered)
Same HTML/CSS/JS, different wrapper:

| Shell | Serves configs | Notes |
|---|---|---|
| **Browser / Cloudflare Pages** | cloud only | zero-install, always-current, phone-friendly. Fewer configs **by nature** (browser security) — a feature, not a gap. |
| **Gateway-served (localhost)** | offline / local | the Gateway hosts the same console; how offline works without any native shell |
| **Native app** *(deferred — Phase 5 decision)* | offline / local / direct / cloud | a single `.exe`; no browser limits (can hit LAN HTTP); can **bundle the Gateway**; **role self-detects** (gateway mode if on the controller link, else console-only). Shell candidates: **Pywebview** (stays in Python — likely first choice) vs **Tauri** (tiny binary, but adds Rust). Decide via a quick spike at Phase 5; the current Python-HTTP-server ↔ vanilla-HTML arch keeps both viable. |

Tauri is a **build tool**, not a platform — it compiles the HTML console into one standalone `.exe`; the user just downloads + runs it (no "Tauri" to install; uses the OS WebView2).

---

## 4. Distribution — the Cloudflare page is the product home
- **"Use online"** → the cloud console (no download).
- **"Download"** → the **Gateway as a single exe** (PyInstaller) with the **console embedded** → run → it serves the console at `localhost` → the whole offline/local system. No Python install.
- Binaries live in **R2** (Pages has a ~25 MB/file limit); the page links/serves them.
- Packaging format is **late-binding** (single combined exe · separate gateway+console exes · Tauri bundle) — components are packaging-agnostic; the format follows how the app evolves.

---

## 5. No-retention model (recap; full text in PROTOCOL §3)
G-code is opaque + always regenerable, so the Gateway **deletes `inbox/<jobId>.*` the instant delivery
succeeds** — the file then lives on the **controller's CNCDISK** (the de-facto retention; same-session re-run
= re-select + Start at the panel). Only `status/<jobId>.json` (metadata, no G-code) persists. Two job types,
keyed off the map: **tracked** (Fusion cut, beacons) vs **deliver-only** (probe/util, no beacons).

---

## 6. Connection-status-driven UI (one UI, adapts)
The console codes against a **connection status** the client reports — not against "cloud"/"local":
`live` (local/direct, zero-lag) · `mirror` (cloud, "updated Xs ago") · `gateway offline` (cloud, asleep).
- A prominent **connection indicator** is always visible.
- **Actions degrade, never break** — when the Gateway is offline (cloud), actions become **queued**, and the UI says so.
- The Gateway publishes a **heartbeat + descriptor** (`gateway/heartbeat.json` → `{machine_id, name, last_seen}`)
  so cloud-mode knows liveness. Offline mode gets liveness for free (the Gateway is serving the page).

---

## 7. Machine identity (safety + which-machine)
The controller has no reliable built-in unique ID over SMB, so identity is **gateway-managed**:
- **Provision once:** write `.bridge-machine.json` (`{id, name}`) to the controller's disk (durable on SYSDISK).
- **Verify before every delivery:** the Gateway reads it; **missing/mismatch → refuse to deliver** (never dump a
  job onto the wrong controller). Identity travels with the controller's disk (survives re-IP; detects swaps).
- Doubles as the heartbeat descriptor + the future multi-tenant gateway↔machine binding.
- **Auto-discovery (later):** scan for the DDCS SMB fingerprint (`CNCDISK`+`SYSDISK`) / an FTDI COM port →
  **propose** gateway role → user **confirms** (never silently claim — two gateways for one controller breaks
  beacon attribution).

---

## 8. Seams left open (future functions — build none now, preclude none)
The principles that cover most of it: **API-first ops** (every capability is a callable op, console is just one
caller) · **view registry** (views are pluggable) · **shared modules** (parser, client) · **backend seam** ·
**client seam** · **tenant prefix**.

| Future function | Seam | Kept-open by |
|---|---|---|
| G-code text view | client `readFile` + view registry | API-first + pluggable views |
| 2D/3D visualiser | shared G-code parser module + view slot | parser written standalone |
| AI agent (MCP) | API-first ops | MCP = thin adapter over the op layer |
| Portable / embed in another app | client as a standalone JS lib | framework-agnostic ES6 modules |
| Multi-user | tenant prefix in Backend + auth at the API | `tenant` param (default ""), API is the auth point |
| **Jog (local motion)** | separate **local-only**, low-latency, **E-stopped** channel — **never** the cloud/observe path | gateway capabilities kept modular; boundary respected |
| Other CNC controllers | a Controller adapter interface | `transfer`/`slave` already isolated |
| Notifications / history | events on status transitions | a subscriber consumes |
| Lint / parse-check | a `lint(gcode)` op | API-first |

**Convergence note (compatibility target, NOT built here):** DDCS Studio is a sibling app (vanilla ES6 modules,
Cloudflare Pages, self-contained bundle). Build the console with the **same conventions** so Studio could later
call `submitJob`, embed the console's modules, or merge into one app/Tauri exe — but the bridge does **not**
build Studio.
