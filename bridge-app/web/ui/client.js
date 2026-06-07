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

// Bearer token for the cloud API (Pages Functions). Empty for the local gateway (no auth). Set via
// `?token=...` (persisted) or localStorage; the gateway ignores Authorization, so it's harmless locally.
function resolveToken() {
  try {
    const q = new URLSearchParams(location.search).get("token");
    if (q != null) { localStorage.setItem("ddcs_token", q); return q; }
    return localStorage.getItem("ddcs_token") || "";
  } catch { return ""; }
}

export function makeClient(opts = {}) {
  const base = resolveBase(opts);   // "" = same-origin (gateway-served / offline). ?api= overrides for dev.
  const tok = opts.token ?? resolveToken();
  const authH = tok ? { Authorization: "Bearer " + tok } : {};

  async function call(path, init = {}) {
    const r = await fetch(base + path, { ...init, headers: { ...authH, ...(init.headers || {}) } });
    if (r.status === 401) throw new Error(`${path} -> 401 (set ?token=… for the cloud API)`);
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
// Which device the gateway is pointed at: configured name, else the controller's own id-file name,
// else the host from the CNCDISK UNC (\\host\share -> host), else "local".
export function deviceName(d) {
  if (!d) return "";
  if (d.machine_name) return d.machine_name;
  if (d.controller_name) return d.controller_name;
  const m = (d.dest || "").match(/^\\\\([^\\]+)\\/);
  if (m) return m[1];
  return "local";
}

export function deriveStatus(client, descriptor) {
  if (!descriptor) return { ok: false, dot: "bad", label: "unreachable", device: "", descriptor: null };
  const device = deviceName(descriptor);
  if ("online" in descriptor) {   // cloud (mirror via heartbeat freshness)
    return descriptor.online
      ? { ok: true, dot: "ok", label: "cloud", device, descriptor }
      : { ok: true, dot: "warn", label: "gateway offline", device, descriptor };
  }
  if (descriptor.controller_connected)   // local gateway, controller reachable
    return { ok: true, dot: "ok", label: "live", device, descriptor };
  return { ok: true, dot: "warn", label: "controller offline", device, descriptor };
}
