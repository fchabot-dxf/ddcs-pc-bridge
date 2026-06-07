// submit.js — submit a job. Beacons ON (default) => instrument client-side (tracked, has map);
// beacons OFF => deliver-only (no map). Settings: count, pacing, var/marker (PROTOCOL §1/§2).
import { el, toast } from "../util.js";
import { instrument, DEFAULTS } from "../instrument/instrument.js";

const field = (labelText, control) => el("div", {}, el("span", { class: "label" }, labelText), control);
const int = (v, d) => { const n = parseInt(v, 10); return Number.isFinite(n) ? n : d; };
const clampInt = (v, lo, hi, d) => Math.min(hi, Math.max(lo, int(v, d)));

export default {
  id: "submit",
  label: "Submit",

  mount(ctx) {
    let file = { name: "", text: "" };

    const drop = el("div", { class: "drop" }, "⤓  Drop a .nc here, or click to choose");
    const input = el("input", { type: "file", accept: ".nc,.tap,.txt,.gcode", style: "display:none" });
    const nameField = el("input", { type: "text", placeholder: "job name (e.g. bracket_v3.nc)", style: "flex:1" });

    const beacons = el("input", { type: "checkbox", checked: "" });
    const count = el("input", { type: "number", value: String(DEFAULTS.max), min: "1", max: "255", style: "width:90px" });
    const pacing = el("select", {},
      el("option", { value: "time" }, "by time (wall-clock)"),
      el("option", { value: "line" }, "by line count"));
    const varN = el("input", { type: "number", value: String(DEFAULTS.varNum), style: "width:70px" });
    const markerV = el("input", { type: "number", value: String(DEFAULTS.markerVar), style: "width:70px" });
    const markerN = el("input", { type: "number", value: String(DEFAULTS.marker), style: "width:70px" });

    const settings = el("div", { class: "block" },
      el("div", { class: "grid-2" }, field("Beacon count (1–255)", count), field("Pacing", pacing)),
      el("details", {},
        el("summary", { class: "muted", style: "cursor:pointer;margin:8px 0" }, "advanced — var / marker (rarely changed; the frame is proven)"),
        el("div", { class: "grid-3" }, field("counter var", varN), field("marker var", markerV), field("marker value", markerN))));

    const btn = el("button", { class: "primary", disabled: "" }, "Submit (tracked)");
    const info = el("div", { class: "hint" });

    const sync = () => {
      settings.classList.toggle("hidden", !beacons.checked);
      btn.textContent = beacons.checked ? "Submit (tracked)" : "Submit (deliver-only)";
    };
    beacons.onchange = sync;

    const load = (f) => {
      const r = new FileReader();
      r.onload = () => {
        file = { name: f.name, text: String(r.result) };
        nameField.value = f.name;
        drop.textContent = `✓ ${f.name} (${file.text.length} bytes)`;
        btn.disabled = false;
      };
      r.readAsText(f);
    };
    drop.onclick = () => input.click();
    input.onchange = (e) => e.target.files[0] && load(e.target.files[0]);
    drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
    drop.ondragleave = () => drop.classList.remove("over");
    drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove("over"); e.dataTransfer.files[0] && load(e.dataTransfer.files[0]); };

    btn.onclick = async () => {
      const name = (nameField.value || file.name || "job.nc").trim();
      btn.disabled = true;
      try {
        let nc = file.text, map;
        if (beacons.checked) {
          const res = instrument(file.text, {
            max: clampInt(count.value, 1, 255, DEFAULTS.max),
            pacing: pacing.value,
            varNum: int(varN.value, DEFAULTS.varNum),
            markerVar: int(markerV.value, DEFAULTS.markerVar),
            marker: int(markerN.value, DEFAULTS.marker),
            source: name,
          });
          nc = res.nc;
          map = res.map;
        }
        const r = await ctx.client.submitJob(name, nc, map);
        toast("Queued " + r.jobId);
        info.textContent = `Queued ${r.jobId} — ${r.tracked ? `tracked (${map.total_beacons} beacons, est ${map.total_est_time_s}s)` : "deliver-only"}`;
      } catch (e) {
        toast("Submit failed: " + e.message, true);
      } finally {
        btn.disabled = false;
      }
    };

    ctx.root.append(el("section", { class: "block" },
      el("div", { class: "section-label" }, "Submit a job"),
      drop, input,
      el("div", { class: "row", style: "margin-top:12px" },
        el("label", { class: "row", style: "gap:6px;cursor:pointer" }, beacons, "Beacons (track progress)")),
      settings,
      el("div", { class: "row", style: "margin-top:12px" }, nameField, btn),
      info,
      el("div", { class: "wiz-usage" },
        "Beacons ON instruments the job (progress tracking). OFF = deliver-only (probe/util). "
        + "Operator presses Cycle Start at the machine.")));
    sync();
  },
};
