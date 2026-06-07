// app.js — the console shell (CONFIGS §6): view registry, poll loop, connection indicator.
// One UI, driven by the connection status the client reports. Same code for every config; only the
// client (and later, what status it derives) changes.
import { makeClient, deriveStatus } from "./client.js";
import { el, clear } from "./util.js";
import submitView from "./views/submit.js";
import queueView from "./views/queue.js";
import filesView from "./views/files.js";
import historyView from "./views/history.js";
import adminView from "./views/admin.js";

const client = makeClient();                       // LocalClient (same-origin); CloudClient/DirectClient later
const VIEWS = [submitView, queueView, filesView, historyView, adminView];

const root = document.getElementById("view");
const tabsEl = document.getElementById("tabs");
const connEl = document.getElementById("conn");

const ctx = { client, root, status: null, refresh };
let active = queueView;

VIEWS.forEach((v) => tabsEl.append(el("div", { class: "tab", onclick: () => activate(v) }, v.label)));

function activate(view) {
  active = view;
  [...tabsEl.children].forEach((t, i) => t.classList.toggle("on", VIEWS[i] === view));
  clear(root);
  view.mount(ctx);
}

function refresh() { activate(active); }

function renderConn() {
  clear(connEl);
  connEl.append(
    el("span", { class: "dot " + (ctx.status?.dot || "bad") }),
    el("span", { class: "conn-label" }, ctx.status?.label || "connecting…"),
  );
}

async function poll() {
  let desc = null;
  try { desc = await client.descriptor(); } catch { desc = null; }
  ctx.status = deriveStatus(client, desc);
  renderConn();
  if (active.onPoll) { try { await active.onPoll(ctx); } catch { /* transient */ } }
}

function clock() { document.getElementById("clock").textContent = new Date().toLocaleTimeString(); }

activate(queueView);
poll(); setInterval(poll, 1500);
clock(); setInterval(clock, 1000);
