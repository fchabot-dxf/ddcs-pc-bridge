// queue.js — the Queue/Tracker view: the active job's progress + the full queue + its events.
// Borderless sections (Studio pattern): a .section-label heading + bare content, spaced by .block.
import { el, fmtEta } from "../util.js";

export default {
  id: "queue",
  label: "Queue · Tracker",

  mount(ctx) {
    this.tracker = el("section", { class: "block" });
    this.queue = el("section", { class: "block" });
    this.events = el("section", { class: "block" });
    ctx.root.append(this.tracker, this.queue, this.events);
    this.onPoll(ctx);
  },

  async onPoll(ctx) {
    let items = [];
    try { items = await ctx.client.listQueue(); } catch { return; }
    const active = items
      .filter((i) => ["running", "delivered", "stalled"].includes(i.state))
      .sort((a, b) => (a.jobId < b.jobId ? 1 : -1))[0];
    this.renderTracker(active);
    this.renderQueue(items);
    this.renderEvents(active);
  },

  renderTracker(j) {
    const c = this.tracker;
    c.replaceChildren(el("div", { class: "section-label" }, "Tracker"));
    if (!j) {
      c.append(el("div", { class: "muted" }, "No active job — submit one, or it appears here on delivery."));
      return;
    }
    const pct = j.percent ?? 0;
    const bar = el("div", { class: "bar" });
    const fill = el("div", { class: "fill" }, pct + "%");
    fill.style.width = pct + "%";
    bar.append(fill);
    c.append(
      el("div", { class: "row spread" },
        el("span", { class: "job" }, j.name || j.jobId),
        el("span", { class: "state s-" + j.state }, (j.state || "").toUpperCase())),
      bar,
      el("div", { class: "grid-3" },
        el("div", { class: "stat" }, el("div", { class: "k" }, "ETA"), el("div", { class: "v" }, fmtEta(j.eta_s))),
        el("div", { class: "stat" }, el("div", { class: "k" }, "Operation"), el("div", { class: "v" }, j.op || "—")),
        el("div", { class: "stat" }, el("div", { class: "k" }, "Line"), el("div", { class: "v" }, j.line != null ? String(j.line) : "—"))),
      el("div", { class: "hint mono" },
        j.last_beacon ? `last beacon ${j.last_beacon}/${j.total_beacons ?? "?"}` : "deliver-only (no beacons)"),
    );
  },

  renderQueue(items) {
    const c = this.queue;
    c.replaceChildren(el("div", { class: "section-label" }, "Queue"));
    if (!items.length) { c.append(el("div", { class: "muted" }, "empty")); return; }
    for (const j of items)
      c.append(el("div", { class: "q" },
        el("span", { class: "pill " + (j.state || "queued") }, j.state || "queued"),
        el("span", { class: "mono" }, j.name || j.jobId)));
  },

  renderEvents(j) {
    const c = this.events;
    c.replaceChildren(el("div", { class: "section-label" }, "Events"));
    const ev = (j && j.events) || [];
    if (!ev.length) { c.append(el("div", { class: "muted" }, "—")); return; }
    const ul = el("ul", { class: "log" });
    [...ev].reverse().forEach((e) => ul.append(el("li", {}, e)));
    c.append(ul);
  },
};
