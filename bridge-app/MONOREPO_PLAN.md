# MONOREPO PLAN — fairy local UI + Studio remote function

> Status: **plan / decided 2026-06-09.** Companion to [`ARCHITECTURE.md`](ARCHITECTURE.md) (module map)
> and [`CONFIGS.md`](CONFIGS.md) (deployment configs). This file is the **split + merge** plan: how the
> one console becomes two specialized faces over a shared core, and how the bridge + DDCS Studio become
> one repo.

## Decisions locked
1. **Monorepo, rooted in DDCS Studio.** The **`DDCS-Studio` repo is the root**; the bridge moves in as a
   `bridge/` folder beside `ddcs-studio-modular/`. Shared JS lives in one place; both faces import it.
   (The long-standing "merge" itch, now committed to. Studio is root because it's the mature product with
   the release flow.) The standalone `ddcs-pc-bridge` repo is **frozen** after the move (GitHub keeps its
   history); all further work happens in the monorepo.
2. **Studio absorbs Submit + Track only.** Files / History / Setup stay **only** on the fairy local UI.
3. **fairy UI never leaves CNC-FAIRY** — served by `server.py` at `localhost`, bundled into `fairy.exe`;
   it is **monitor + gateway control**, no submit.
4. **Studio replaces the Cloudflare Pages bare console** as the remote face. The Worker + R2 + `/api`
   contract are **unchanged** — Studio is just a new client of the same API.

---

## North star — two faces, one shared core
```
   fairy LOCAL UI  (CNC-FAIRY only)            STUDIO  (anywhere: design PC, phone)
   served by server.py @ localhost             Cloudflare Pages (replaces bare console)
   ┌──────────────────────────┐               ┌──────────────────────────────┐
   │ Queue·Tracker (live)      │               │ Submit (author→instrument)   │
   │ Files (CNCDISK)           │               │ Track (mirror, ~3s)          │
   │ History                   │               │ + Studio's authoring/wizards │
   │ Setup/Admin (gateway cfg) │               └──────────────┬───────────────┘
   │ Gateway control           │                              │
   └──────────────┬────────────┘                              │
                  │              ┌─────────── shared/js ───────┴──────┐
                  └──────────────┤ client.js · instrument/ · tracker  │
                  imports        │ view · style tokens                │
                                 └────────────────────────────────────┘
   meet at:  localhost /api  (local)          R2 via Worker /api  (remote)
   contract: shared/protocol/PROTOCOL.md  +  ops.py /api surface  (FROZEN, proven)
```
Neither face knows about the other. They rendezvous at R2 (remote) or localhost (local). Nothing new in
the seam — `PROTOCOL.md` + the `/api` ops surface already exist and are proven.

## View allocation
| Current view | fairy local UI | Studio | Notes |
|---|:---:|:---:|---|
| Queue · Tracker | ✅ live, zero-lag | ✅ mirror | shared tracker module |
| Submit (+ instrumenter) | ❌ | ✅ **the** remote function | uses shared `instrument/` |
| Files (CNCDISK) | ✅ | ❌ | file ops belong at the machine |
| History | ✅ | ❌ | (revisit if a remote view is wanted) |
| Setup / Admin (gateway cfg) | ✅ local-only | ❌ | cloud can't configure the gateway, by design |
| Gateway control (pause/cancel/clear/reconnect) | ✅ new | ❌ | the operator's at-machine controls |

## The shared core (`shared/js/`)
Three things both faces consume — extracted once, imported by both:
- **`client.js`** — the `/api` seam (already abstracts local-gateway vs cloud-R2 via `?api=`/`?token=`).
- **`instrument/`** (`instrument.js` + `gcode-parse.js` + `selftest.mjs`) — the beacon instrumenter
  (the `checkpoint_insert.py` port; its self-test is the spec). **Studio's Submit uses THIS**, not a
  reimplementation over its own `gcodeParser.js`.
- **Tracker/Queue view + style tokens** — both faces render progress identically.

> **Carry-over (open):** the shared instrumenter places a beacon on **any** Z-rise (`zup = (nz-z) > eps`).
> The `eee.nc` analysis showed this puts ~2/3 of beacons *mid-cut* in a morphed spiral. A
> **pure-vertical-retract option** (require X/Y held) belongs here in `shared/js/instrument/`, behind a
> setting, gated on the live stall-test. Benefits both faces at once.

---

## Target monorepo layout
```
DDCS-Studio/                      (the Studio repo IS the monorepo root — its remote, its release flow)
  ddcs-studio-modular/            the Studio app (authoring; gains Submit + Track)
  bridge/                         the bridge, imported here — SOURCE ONLY, no nested .git
    bridge-app/fairy/             Python gateway (unchanged)
    bridge-app/web/ui/            fairy LOCAL UI shell — monitor + control only
    bridge-app/shared/PROTOCOL.md the contract (doc)
    controllers/ …                controller research + findings
  shared/js/                      THE shared ES6 modules (client, instrument, tracker view, tokens)
  release.py                      Studio's existing release flow (unchanged)
```
Both `ddcs-studio-modular` and `bridge/web/ui` are vanilla ES6, no registry needed — they import shared
modules by relative path. The only build wrinkle: each serving context must include `shared/js/` (fairy
`server.py` static-serves it; Studio's `scripts/bundle.cjs` must follow imports into `shared/js/`).
Tracked as a P2 integration task.

## Migration phases (incremental — low-risk first; the git merge comes late)
- **P1 — Freeze the seam.** `/api` ops + `PROTOCOL.md`. ✅ *done.*
- **P2 — Extract shared modules.** Move `client.js` + `instrument/` + tracker view + style tokens into
  `shared/js/`; fairy local UI imports from there. Internal refactor only; `selftest.mjs` stays green.
  **No Studio involvement, fully reversible.**
- **P3 — Slim the fairy local UI.** Local shell = Queue/Tracker + Files + History + Setup + gateway
  control. Remove Submit from the local shell (it lives in `shared/` for Studio). Lock `server.py` to
  `127.0.0.1`; bundle into `fairy.exe`.
- **P4 — Bring Studio in + wire it.** `git subtree add --prefix=studio <studio-repo> main` (preserves
  Studio's history + release flow). Studio imports the shared modules to build **Submit + Track**,
  building on its existing specs (`addstudiotransfer.md` = transfer/submit, `addstudioverify.md` = the
  lint gate). Instrumentation = the shared `instrument/`.
- **P5 — Repoint the remote face.** Cloudflare Pages → Studio. Retire the bare cloud console. Worker +
  R2 + `/api` unchanged.

## Open sub-decisions / risks
- **Monorepo root = the bridge repo** (recommended: it holds the protocol, gateway, and controller
  research; Studio comes in under `studio/`). Confirm vs. a neutral new root.
- **Studio's history** comes in via **git subtree** (preserves its `release.py`/versioning). Don't flatten.
- **Bundler reach:** Studio's `bundle.cjs` must inline `../shared/js/` — verify the standalone/exe build.
- **Two `gcode` parsers:** Studio keeps `gcodeParser.js` for *authoring*; the shared `instrument/` does
  *beaconing*. Keep them distinct (different jobs) unless a later unification is deliberate.
- **fairy local Submit fallback:** currently **dropped** (monitor+control only). Revisit only if running a
  job from the machine PC without Studio becomes a real need.
