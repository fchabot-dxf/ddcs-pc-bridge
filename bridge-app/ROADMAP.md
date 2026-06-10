# ROADMAP — DDCS Bridge build phases

Scoped to the **bridge only** (DDCS Studio is a *compatibility target*, not built here — see
[`CONFIGS.md`](CONFIGS.md) §8). Each phase ships something usable; seams get baked in as we pass them.
Vocabulary + configs + seam map: [`CONFIGS.md`](CONFIGS.md). The contract: [`shared/PROTOCOL.md`](shared/PROTOCOL.md).

**Foundation already built** (the Gateway core): poller · transfer · slave (sim + Modbus) · cncdisk explorer ·
backend (local + R2) · two job types · no-retention. 24 self-test checks green; **SMB delivery + CNCDISK
explorer proven live on the V4.1 (2026-06-07).**

---

## Phase 0 — Capture & checkpoint  *(no new app code)*
- **Goal:** design recorded; working Gateway committed.
- **Build:** `CONFIGS.md`, `ROADMAP.md`; vocab standardized (console/gateway/rendezvous; Worker "gateway"→"API").
- **Verify:** docs consistent; `--self-test` + `--demo` green; clean commit of `fairy/` + docs.

## Phase 1 — Gateway: ops API + local-server + identity + heartbeat
- **Goal:** the Gateway exposes a clean **operations API** any client can call, and can serve over localhost.
- **Build:**
  - Op layer: `submitJob` · `getStatus` · `listFiles` · `deleteFile` · `readFile` · `getDescriptor`.
  - **Local-server mode** (HTTP serving those ops + later the console) — the offline/local host.
  - **Machine identity:** provision `.bridge-machine.json`; **verify-before-deliver** (mismatch → refuse).
  - **Heartbeat:** publish `gateway/heartbeat.json` (`{machine_id, name, last_seen}`).
- **Verify:** curl the local API; identity mismatch refuses delivery (live on V4.1); heartbeat written.
- **Seam:** this API = the future **MCP / embeddable** surface.

## Phase 2 — Console (offline end-to-end)  ⭐ first usable product — ✅ DONE
- **Goal:** browser at the Gateway's `localhost` → full submit / track / files / admin, no cloud.
- **Build:** vanilla **ES6 modules + manager classes**; **view registry**; **client seam** (`LocalClient` first);
  views **Submit · Queue/Tracker · Files · Admin**; **connection-status-aware** UI (live/mirror/offline);
  self-contained (no CDN).
- **Verify:** Gateway local-server + browser → deliver-only submit, sim-beacon tracked job, file list+delete,
  admin config. **Offline config works end-to-end.**

## Phase 3 — Cloud path  — ✅ DONE (deployed live 2026-06-07)
- **Goal:** cloud config — submit from anywhere; Gateway polls R2.
- **Built:** **Pages Functions** R2 API (`web/functions/api/[[path]].js`, same-origin as the console,
  bearer-token auth) — the same `/api` contract the gateway serves locally, backed by R2; console client
  gains `?api=`/`?token=` + Authorization; cloud connection status from `gateway/heartbeat.json`;
  `wrangler.toml` (R2 binding) + `web/DEPLOY.md`. **Verified locally on emulated R2** (`wrangler pages dev`):
  submit→queue→history→delete-command + console renders with "gateway offline" until a heartbeat exists.
- **Live (DONE 2026-06-07):** R2 **S3 token** created + `--r2-check` PASSED; `wrangler pages deploy` →
  console + Pages Functions live at **https://ddcs-bridge.pages.dev** (`ACCESS_TOKEN` secret set, R2
  binding `BUCKET`). Cloud API verified: no-token→401, descriptor→`backend:r2`, POST job→tracked (real
  R2 write). Gateway cloud mode runs on CNC-FAIRY; **not yet run against a live machine — that's Phase 6.**
  See [`web/DEPLOY.md`](web/DEPLOY.md).

## Phase 4 — JS instrumenter + beacon settings — ✅ DONE
- **Goal:** Submit turns a raw `.nc` into a tracked job in the browser.
- **Build:** port `checkpoint_insert.py` → `gcode-parse.js` + `instrument.js` (**self-test parity** with Python);
  **beacon toggle** (on→tracked / off→deliver-only) + settings (**count · pacing · var/marker**).
- **Verify:** JS self-test matches Python on the frame; toggle drives tracked vs deliver-only.

## Phase 5 — Packaging / distribution
- **Goal:** download one exe from the page → run → offline system.
- **Decision to make here — native shell:** spike **Tauri vs Pywebview** and pick by feel/deploy.
  - **Pywebview** (recommended to evaluate first): stays in the **Python** ecosystem — wrap the Python
    gateway + the vanilla ES6 console into one window/`.exe` with **no Rust context-switch**. Likely the
    fastest path given the gateway is already Python.
  - **Tauri**: tiny binary, OS WebView2, auto-update — but a third ecosystem (Rust) just to render a window.
  - Either way it's just a wrapper around the **same Python gateway + same HTML console** — the current
    architecture (local Python HTTP server ↔ vanilla browser UI) keeps **both paths viable**, so this stays
    a late, low-cost decision.
- **Build:** **PyInstaller** single exe (Gateway + embedded console) and/or the chosen native shell;
  **Download** button on the page → exe hosted on **R2**.
- **Gateway lifecycle (decided 2026-06-07):** the gateway is **not** started from the web console (it
  *serves* the console; the cloud console can't reach it by design). Start = the exe + **Task Scheduler
  auto-start (boot + resume-from-sleep)** + a future **tray launcher** (start/stop). Small touches:
  **auto-open the browser on `--serve`**, and optional **Admin restart/stop** (local mode only).
- **Verify:** run the exe on a clean profile → localhost console works. (Code-signing / SmartScreen = later.)

## Phase 6 — Live on the Expert
- **Goal:** the one thing only testable there — real Modbus beacons end-to-end.
- **Verify:** instrumented job → delivered → operator Start → beacons → console bar advances; done vs stalled.

---

## Deferred (seams open; build when wanted — see CONFIGS §8)
Tauri shell (windowed exe + role auto-detect) · **MCP agent server** · multi-user (tenant + auth) ·
G-code text view + 2D/3D visualiser · **jog** (separate local-only, E-stopped channel — never the cloud path) ·
notifications / history / other controllers.

## Milestones
- **P2** = usable offline product · **P3** = cloud works · **P5** = downloadable · **P6** = full tracked on real hardware.
