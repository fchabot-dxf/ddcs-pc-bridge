// Cloudflare Pages Function — the CLOUD api for the console (CONFIGS: cloud config).
// Serves the SAME /api/* contract the gateway serves locally, but backed by the R2 bucket instead of
// local ops. Colocated with the static console (Pages) so it's same-origin — the console's client needs
// no change. The browser never holds R2 keys; this runs on the edge with the R2 binding + a bearer token.
//
// Bindings (Pages project): R2 bucket -> env.BUCKET ; secret -> env.ACCESS_TOKEN (the shared access token).
// [TO TEST live once the Pages project + R2 binding + token exist.]

const JH = { "content-type": "application/json", "access-control-allow-origin": "*" };
const json = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: JH });

const HEARTBEAT = "gateway/heartbeat.json";
const ONLINE_S = 90;   // gateway is "offline" if its heartbeat is older than this

const slug = (name) => {
  const base = name.includes(".") ? name.slice(0, name.lastIndexOf(".")) : name;
  return base.replace(/[^A-Za-z0-9_.-]+/g, "_").replace(/^_+|_+$/g, "") || "job";
};
const jobId = (name) => {
  const d = new Date(), p = (n, w = 2) => String(n).padStart(w, "0");
  const ts = `${d.getUTCFullYear()}${p(d.getUTCMonth() + 1)}${p(d.getUTCDate())}T${p(d.getUTCHours())}${p(d.getUTCMinutes())}${p(d.getUTCSeconds())}`;
  return `${ts}_${p(d.getUTCMilliseconds(), 3)}000-${slug(name)}`;
};
async function readJSON(bucket, key) {
  const o = await bucket.get(key);
  if (!o) return null;
  try { return JSON.parse(await o.text()); } catch { return null; }
}
async function listJSON(bucket, prefix) {
  const out = [];
  let cursor;
  do {
    const l = await bucket.list({ prefix, cursor });
    for (const o of l.objects) if (o.key.endsWith(".json")) { const v = await readJSON(bucket, o.key); if (v) out.push(v); }
    cursor = l.truncated ? l.cursor : undefined;
  } while (cursor);
  return out;
}

export async function onRequest(context) {
  const { request, env, params } = context;
  const url = new URL(request.url);
  const path = "/" + (Array.isArray(params.path) ? params.path.join("/") : (params.path || ""));
  const m = request.method;

  if (m === "OPTIONS")
    return new Response(null, { status: 204, headers: {
      "access-control-allow-origin": "*", "access-control-allow-methods": "GET,POST,OPTIONS",
      "access-control-allow-headers": "content-type,authorization" } });

  if (env.ACCESS_TOKEN && (request.headers.get("authorization") || "") !== `Bearer ${env.ACCESS_TOKEN}`)
    return json({ error: "unauthorized" }, 401);

  const bucket = env.BUCKET;
  if (!bucket) return json({ error: "R2 binding 'BUCKET' not configured" }, 500);

  try {
    if (m === "GET" && path === "/descriptor") {
      const hb = await readJSON(bucket, HEARTBEAT);
      if (!hb) return json({ backend: "r2", online: false, controller_connected: false, machine_name: null });
      const age = (Date.now() - Date.parse(hb.last_seen || 0)) / 1000;
      return json({ ...hb, backend: "r2", online: age <= ONLINE_S, age_s: Math.round(age) });
    }
    if (m === "GET" && path === "/queue") {
      const statuses = await listJSON(bucket, "status/");
      const seen = new Set(statuses.map((s) => s.jobId));
      const items = [...statuses];
      const inbox = await bucket.list({ prefix: "inbox/" });
      for (const o of inbox.objects) if (o.key.endsWith(".nc")) {
        const id = o.key.slice("inbox/".length, -3);
        if (!seen.has(id)) items.push({ jobId: id, state: "queued" });
      }
      items.sort((a, b) => (a.jobId < b.jobId ? -1 : 1));
      return json(items);
    }
    if (m === "GET" && path === "/status") {
      const s = await readJSON(bucket, `status/${url.searchParams.get("id") || ""}.json`);
      return s ? json(s) : json({ error: "no such job" }, 404);
    }
    if (m === "GET" && path === "/history") {
      const limit = parseInt(url.searchParams.get("limit") || "100", 10) || 100;
      const rows = await listJSON(bucket, "history/");
      rows.sort((a, b) => ((a.recorded_at || "") < (b.recorded_at || "") ? 1 : -1));
      return json(rows.slice(0, limit));
    }
    if (m === "GET" && path === "/files") {
      return json((await readJSON(bucket, "cncdisk/index.json")) || { path: "", files: [], error: "no listing published yet" });
    }
    if (m === "GET" && path === "/file") {
      return json({ ok: false, error: "file view is not available in cloud mode" });
    }
    if (m === "POST" && path === "/jobs") {
      const b = await request.json().catch(() => ({}));
      if (!b.name || b.nc == null) return json({ error: "name and nc required" }, 400);
      const id = jobId(b.name);
      await bucket.put(`inbox/${id}.nc`, b.nc, { httpMetadata: { contentType: "text/plain" } });
      if (b.map) await bucket.put(`inbox/${id}.map.json`, JSON.stringify(b.map), { httpMetadata: { contentType: "application/json" } });
      return json({ jobId: id, name: b.name, tracked: !!(b.map && b.map.total_beacons) });
    }
    if (m === "POST" && path === "/files/delete") {
      const b = await request.json().catch(() => ({}));
      const id = jobId("cmd");
      await bucket.put(`commands/${id}.json`, JSON.stringify({ op: "delete", target: b.name || "" }),
                       { httpMetadata: { contentType: "application/json" } });
      return json({ ok: true, queued: true });
    }
    return json({ error: "not found" }, 404);
  } catch (e) {
    return json({ error: String(e) }, 500);
  }
}
