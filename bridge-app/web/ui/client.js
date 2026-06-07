// client.js — the transport seam (CONFIGS §1/§2).
//
// The UI codes against THIS interface, never against "cloud" vs "local". Today there's one impl,
// LocalClient, talking to the gateway's same-origin /api (gateway-served console). Later a CloudClient
// (→ the Worker/API) and a DirectClient (→ gateway over the LAN) implement the same shape — the views
// don't change. Keeping this the single seam is what makes the configs (CONFIGS §2) one codebase.

// Resolve the API base. Default "" = same-origin (gateway-served / offline). Override with an `?api=URL`
// query param (persisted to localStorage) so you can serve the UI from anywhere (e.g. VS Code Live
// Server on :5500) and point it at the gateway on :8799. Also the seam for the future Cloud/Direct clients.
function resolveBase(opts) {
  if (opts.base != null) return opts.base;
  try {
    const q = new URLSearchParams(location.search).get("api");
    if (q != null) { localStorage.setItem("ddcs_api", q); return q; }
    return localStorage.getItem("ddcs_api") || "";
  } catch { return ""; }
}

export function makeClient(opts = {}) {
  const base = resolveBase(opts);   // "" = same-origin (gateway-served / offline). ?api= overrides for dev.

  async function call(path, init) {
    const r = await fetch(base + path, init);
    if (!r.ok) throw new Error(`${path} -> HTTP ${r.status}`);
    return r.json();
  }
  const postJSON = (path, body) =>
    call(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

  return {
    mode: base ? "remote" : "local",
    descriptor: () => call("/api/descriptor"),
    listQueue: () => call("/api/queue"),
    listHistory: (limit = 100) => call("/api/history?limit=" + limit),
    getStatus: (id) => call("/api/status?id=" + encodeURIComponent(id)),
    listFiles: () => call("/api/files"),
    readFile: (name) => call("/api/file?name=" + encodeURIComponent(name)),
    deleteFile: (name) => postJSON("/api/files/delete", { name }),
    submitJob: (name, nc, map) => postJSON("/api/jobs", { name, nc, map }),
  };
}

// Connection status the UI renders (CONFIGS §6). For LocalClient a reachable gateway == "live".
// (CloudClient will add the "mirror" / "offline" interpretations from the heartbeat later.)
export function deriveStatus(client, descriptor) {
  if (!descriptor) return { ok: false, dot: "bad", label: "gateway unreachable" };
  const name = descriptor.machine_name || descriptor.controller_name || "gateway";
  if (descriptor.controller_connected)
    return { ok: true, dot: "ok", label: `live · ${name}`, descriptor };
  return { ok: true, dot: "warn", label: `gateway up · controller offline`, descriptor };
}
