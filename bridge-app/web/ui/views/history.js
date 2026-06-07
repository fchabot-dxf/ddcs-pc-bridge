// history.js — finished-job history: name, final state, run duration, when. Reads the durable
// history seam (gateway records every terminal job). Borderless section (Studio pattern).
import { el, fmtEta } from "../util.js";

const fmtWhen = (iso) => (iso ? iso.replace("T", " ").replace("Z", "") : "—");
const fmtDur = (s) => (s == null ? "—" : fmtEta(s));

export default {
  id: "history",
  label: "History",

  mount(ctx) {
    this.card = el("section", { class: "block" });
    ctx.root.append(this.card);
    this.onPoll(ctx);
  },

  async onPoll(ctx) {
    let rows = [];
    try { rows = await ctx.client.listHistory(); } catch { return; }
    const c = this.card;
    c.replaceChildren(el("div", { class: "section-label" }, "History"));
    if (!rows.length) { c.append(el("div", { class: "muted" }, "no finished jobs yet")); return; }
    const tbl = el("table", {}, el("tr", {},
      el("th", {}, "job"), el("th", {}, "result"), el("th", {}, "duration"), el("th", {}, "finished")));
    for (const r of rows) {
      tbl.append(el("tr", {},
        el("td", { class: "mono" }, r.name || r.jobId),
        el("td", {}, el("span", { class: "pill " + (r.final_state || "") }, r.final_state || "—")),
        el("td", { class: "mono" }, fmtDur(r.duration_s)),
        el("td", { class: "mono" }, fmtWhen(r.ended_at))));
    }
    c.append(tbl);
  },
};
