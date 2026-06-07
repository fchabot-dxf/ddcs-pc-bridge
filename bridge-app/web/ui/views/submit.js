// submit.js — submit a job. Phase 2 is deliver-only (no map => no beacons); the beacon toggle +
// client-side instrumenter arrive in Phase 4. Borderless section (Studio pattern).
import { el, toast } from "../util.js";

export default {
  id: "submit",
  label: "Submit",

  mount(ctx) {
    let file = { name: "", text: "" };

    const drop = el("div", { class: "drop" }, "⤓  Drop a .nc here, or click to choose");
    const input = el("input", { type: "file", accept: ".nc,.tap,.txt,.gcode", style: "display:none" });
    const nameField = el("input", { type: "text", placeholder: "job name (e.g. bracket_v3.nc)", style: "flex:1" });
    const btn = el("button", { class: "primary", disabled: "" }, "Submit (deliver-only)");
    const info = el("div", { class: "hint" });

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
        const r = await ctx.client.submitJob(name, file.text);
        toast("Queued " + r.jobId);
        info.textContent = `Queued ${r.jobId} (${r.tracked ? "tracked" : "deliver-only"})`;
      } catch (e) {
        toast("Submit failed: " + e.message, true);
      } finally {
        btn.disabled = false;
      }
    };

    ctx.root.append(
      el("section", { class: "block" },
        el("div", { class: "section-label" }, "Submit a job"),
        drop, input,
        el("div", { class: "row", style: "margin-top:12px" }, nameField, btn),
        info,
        el("div", { class: "wiz-usage" },
          "Phase 2: deliver-only (no beacons). The beacon on/off toggle + settings arrive in Phase 4.")),
    );
  },
};
