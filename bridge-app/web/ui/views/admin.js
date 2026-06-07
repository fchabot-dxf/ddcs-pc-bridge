// admin.js — the Setup view. On a LOCAL gateway it's an editable form (machine name, controller disk,
// beacons) with a clear connection status. On the CLOUD console it's read-only (the cloud can't reach
// into the gateway — configure it on the machine PC). A form view: mounted on tab click, not polled.
import { el, toast } from "../util.js";

export default {
  id: "admin",
  label: "Setup",

  async mount(ctx) {
    this.card = el("section", { class: "block" });
    ctx.root.append(this.card);
    await this.render(ctx);
  },

  async render(ctx) {
    let d;
    try { d = await ctx.client.descriptor(); }
    catch { this.card.replaceChildren(el("div", { class: "muted" }, "gateway unreachable")); return; }
    if ("online" in d) return this.renderCloud(d);          // cloud console: read-only
    let cfg = {};
    try { cfg = await ctx.client.getConfig(); } catch { /* keep defaults */ }
    this.renderSetup(ctx, d, cfg);
  },

  renderCloud(d) {
    const rows = [
      ["machine name", d.machine_name || "—"],
      ["controller", d.dest || "—"],
      ["gateway online", d.online ? "yes" : "no"],
      ["controller connected", d.controller_connected ? "yes" : "no"],
      ["backend", d.backend],
    ];
    const tbl = el("table");
    for (const [k, v] of rows) tbl.append(el("tr", {}, el("td", {}, k), el("td", { class: "mono" }, String(v))));
    this.card.replaceChildren(
      el("div", { class: "section-label" }, "Gateway (cloud view)"),
      tbl,
      el("div", { class: "wiz-usage" },
        "This is the cloud console — it can't configure the gateway (the gateway is outbound-only). "
        + "Set it up in the Setup tab of the gateway's own console, on the machine PC."));
  },

  renderSetup(ctx, d, cfg) {
    const dest = (cfg.dest || "");
    const isRemote = dest.startsWith("\\\\") || dest.startsWith("//");
    const statusText = !dest ? "no controller set — enter the controller disk below"
      : !isRemote ? "sandbox (local folder)"
      : d.controller_connected ? "live — connected to " + dest
      : "controller offline — " + dest + " not reachable";
    const statusDot = (!dest || !isRemote || !d.controller_connected) ? "warn" : "ok";

    const name = el("input", { type: "text", value: cfg.machine_name || "", placeholder: "e.g. Ultimate Bee" });
    const destField = el("input", { type: "text", value: dest, placeholder: "\\\\10.0.0.50\\cncdisk", style: "width:100%" });
    const beacons = el("input", { type: "checkbox" });
    beacons.checked = !!cfg.enable_slave;
    const save = el("button", { class: "primary" }, "Save");
    const info = el("div", { class: "hint" });

    save.onclick = async () => {
      save.disabled = true;
      try {
        const r = await ctx.client.setConfig({
          machine_name: name.value, dest: destField.value.trim(), enable_slave: beacons.checked,
        });
        if (!r.ok) { toast(r.error || "save failed", true); info.textContent = r.error || ""; }
        else {
          toast("Saved");
          info.textContent = r.restart_needed ? "Saved. Beacons change needs a gateway restart." : "Saved + applied.";
          await this.render(ctx);
        }
      } catch (e) { toast("save failed: " + e.message, true); }
      finally { save.disabled = false; }
    };

    this.card.replaceChildren(
      el("div", { class: "section-label" }, "Connection"),
      el("div", { class: "row" }, el("span", { class: "dot " + statusDot }), el("span", {}, statusText)),

      el("div", { class: "section-label", style: "margin-top:18px" }, "Setup"),
      el("div", {}, el("span", { class: "label" }, "Machine name"), name),
      el("div", { style: "margin-top:10px" },
        el("span", { class: "label" }, "Controller disk (network share)"),
        destField,
        el("span", { class: "hint" }, "Must be a network share, e.g. \\\\10.0.0.50\\cncdisk — local folders aren't allowed.")),
      el("label", { class: "row", style: "margin-top:12px;gap:6px;cursor:pointer" },
        beacons, "Beacons (Modbus progress — Expert only; leave off for V4.1)"),
      el("div", { class: "row", style: "margin-top:14px" }, save), info,
      el("div", { class: "wiz-usage" }, `gateway v${d.version || "?"} · backend ${d.backend || "?"}`));
  },
};
