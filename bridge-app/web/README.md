# web/ — the Console (App 1)

The operator-facing UI: **Submit · Queue/Tracker · Files (CNCDISK) · Admin**. One vanilla **HTML/CSS/JS**
codebase (no framework, no CDN, no build step) so the *same* files run in a browser, served by the
**Gateway** locally (offline/local configs), deployed to **Cloudflare Pages** (cloud config), or wrapped
in a native shell later. See [`../CONFIGS.md`](../CONFIGS.md) for the config/shell matrix.

## Structure
```
web/
  ui/                       the console (static; served by gateway or Pages)
    index.html              shell: header + tabs + view mount
    styles.css              tokens + base classes shared with DDCS Studio (data-theme swappable)
    app.js                  shell: view registry, poll loop, connection indicator
    client.js               the transport SEAM (LocalClient; ?api= override; Cloud/Direct later)
    util.js                 tiny DOM helpers (el/clear/toast)
    views/                  submit.js · queue.js · files.js · history.js · admin.js
    instrument/             gcode-parse.js + instrument.js (JS port of checkpoint_insert.py) · selftest.mjs
  worker/                   (Phase 3) authed R2 API — so the browser never holds R2 keys
```

## Run / view
- **Gateway-served (offline/local):** start the gateway with `--serve --console web/ui`, open `http://<host>:8765`.
- **Any static host (dev, e.g. VS Code Live Server):** open `index.html` and append **`?api=http://<gateway-host>:8765`**
  to point the client at the gateway (CORS is open on the gateway; the base is remembered in localStorage).
- **Cloud (Phase 3):** deployed to Cloudflare Pages; the client talks to the Worker/API.

## Conventions (shared with DDCS Studio — so stylesheets/themes swap)
Tokens: `--bg --panel --accent --text --text-dim --border --radius --success --danger --warn` (+ `--panel2 --accent2 --bar`),
restyled via `[data-theme]`. Base classes match Studio: `app-header`/`hdr-*`, `button`/`op-btn`/`primary`,
`grid-2/3/4`, `label`/`section-label`, `hint`, `preview-block`, `viz-*` (reserved for the future visualiser),
`hidden`, `pre`. Sections are **borderless** (a `section-label` heading + bare content).
