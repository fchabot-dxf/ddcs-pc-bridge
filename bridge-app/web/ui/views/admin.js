// admin.js — gateway/machine info + identity (local-gateway only; cloud console hides this later).
import { el } from "../util.js";

export default {
  id: "admin",
  label: "Admin",

  mount(ctx) {
    this.card = el("section", { class: "block" });
    ctx.root.append(this.card);
    this.onPoll(ctx);
  },

  async onPoll(ctx) {
    let d;
    try { d = await ctx.client.descriptor(); }
    catch { this.card.replaceChildren(el("div", { class: "muted" }, "gateway unreachable")); return; }
    const rows = [
      ["machine name", d.machine_name || "(unset)"],
      ["machine id (expected)", d.machine_id || "(unconfigured — verify skipped)"],
      ["controller id (on disk)", d.controller_id || "—"],
      ["controller name (on disk)", d.controller_name || "—"],
      ["controller connected", d.controller_connected ? "yes" : "no"],
      ["backend", d.backend],
      ["gateway version", d.version],
    ];
    const tbl = el("table");
    for (const [k, v] of rows)
      tbl.append(el("tr", {}, el("td", {}, k), el("td", { class: "mono" }, String(v))));
    this.card.replaceChildren(
      el("div", { class: "section-label" }, "Gateway / machine"),
      tbl,
      el("div", { class: "wiz-usage" },
        "Set identity on the gateway: --provision (write id to the controller) and --machine-id/--name. "
        + "In-UI config editing comes in a later pass."),
    );
  },
};
