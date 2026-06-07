// files.js — the CNCDISK explorer: list the controller's files, view G-code (preview-block), delete (safe).
import { el, toast } from "../util.js";

export default {
  id: "files",
  label: "Files (CNCDISK)",

  mount(ctx) {
    this.list = el("section", { class: "block" });
    this.viewer = el("section", { class: "block hidden" });
    ctx.root.append(this.list, this.viewer);
    this.onPoll(ctx);
  },

  async onPoll(ctx) {
    let idx;
    try { idx = await ctx.client.listFiles(); } catch { return; }
    const c = this.list;
    c.replaceChildren(el("div", { class: "section-label" }, "CNCDISK · " + (idx.path || "")));
    if (idx.error) { c.append(el("div", { class: "muted" }, "unreachable: " + idx.error)); return; }
    if (!idx.files.length) { c.append(el("div", { class: "muted" }, "(empty)")); return; }
    const tbl = el("table", {}, el("tr", {}, el("th", {}, "name"), el("th", {}, "size"), el("th", {}, "")));
    for (const f of idx.files) {
      tbl.append(el("tr", {},
        el("td", { class: "mono" }, f.name),
        el("td", { class: "mono" }, String(f.size)),
        el("td", {}, el("div", { class: "row" },
          el("button", { class: "op-btn", onclick: () => this.view(ctx, f.name) }, "view"),
          el("button", { class: "op-btn danger", onclick: () => this.del(ctx, f.name) }, "delete")))));
    }
    c.append(tbl);
  },

  async del(ctx, name) {
    if (!confirm(`Delete ${name} from the controller?`)) return;
    try {
      const r = await ctx.client.deleteFile(name);
      r.ok ? toast("Deleted " + name) : toast("Delete refused: " + r.error, true);
      this.onPoll(ctx);
    } catch (e) { toast("Delete failed: " + e.message, true); }
  },

  async view(ctx, name) {
    try {
      const r = await ctx.client.readFile(name);
      const v = this.viewer;
      v.classList.remove("hidden");
      v.replaceChildren();
      if (!r.ok) { v.append(el("div", { class: "muted" }, "cannot read: " + r.error)); return; }
      v.append(
        el("div", { class: "row spread" },
          el("div", { class: "section-label" }, "G-code · " + name),
          el("button", { class: "op-btn", onclick: () => v.classList.add("hidden") }, "close")),
        el("div", { class: "preview-block" }, el("pre", {}, r.content)));
    } catch (e) { toast("Read failed: " + e.message, true); }
  },
};
