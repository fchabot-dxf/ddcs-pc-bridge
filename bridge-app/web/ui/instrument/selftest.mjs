// Node self-test for the JS instrumenter — mirrors checkpoint_insert.py's self_test (the spec).
//   node web/instrument/selftest.mjs
import { instrument, msetdataCall } from "./instrument.js";

const job = [
  "(Job header)", "G90 G54",
  "(2D Contour1)", "G0 X0 Y0 Z5", "G1 Z-1 F100", "G1 X50 F600", "G0 Z5",     // retract 1
  "(2D Contour2)", "G0 X0 Y10", "G1 Z-1 F100", "G1 X50 F600", "G0 Z5",        // retract 2
  "(Drill)", "G0 X0 Y20", "G1 Z-3 F50", "G0 Z5",                              // retract 3
  "G0 Z25",                                                                    // final safe Z (zup)
  "M30", "",
].join("\n");

const { nc, map } = instrument(job, { max: 255, source: "self-test" });
const lines = nc.split("\n");
const mset = msetdataCall();
let ok = true;
const check = (c, l) => { console.log(`  [${c ? "ok" : "FAIL"}] ${l}`); ok = ok && c; };

const pushes = lines.map((l, i) => [l, i]).filter(([l]) => l.trim() === mset).map(([, i]) => i);
check(pushes.length === map.total_beacons, `push count == map beacons (${map.total_beacons})`);
check(pushes.every((i) => lines[i - 1].trim().startsWith("#250 =")), "every MSETDATA preceded by #250 = n");

const markers = lines.map((l, i) => [l, i]).filter(([l]) => l.trim() === "#251 = 111").map(([, i]) => i);
check(markers.length === 1 && markers[0] < pushes[0], "marker #251=111 set once, before first push");

const nums = pushes.map((i) => parseInt(lines[i - 1].split("=")[1], 10));
check(JSON.stringify(nums) === JSON.stringify(nums.map((_, k) => k + 1)), "counter is 1..N strictly increasing");
check(Math.max(...nums) <= 255, "counter never exceeds one byte (255)");

const src = job.split("\n");
let landed = true;
for (const b of map.beacons) {
  if (b.complete) continue;
  const s = src[b.orig_line - 1];
  landed = landed && (s.includes("Z5") || s.includes("Z25")) && s.includes("G0");
}
check(landed, "non-final beacons land on Z-up (retract) lines only");

const last = map.beacons[map.beacons.length - 1];
check(last.complete && (last.percent === 100.0 || last.percent === null), "final beacon flagged complete at ~100%");

const pcts = map.beacons.map((b) => b.percent).filter((p) => p !== null);
check(JSON.stringify(pcts) === JSON.stringify([...pcts].sort((a, b) => a - b)), "percent is monotonic non-decreasing");

check(map.beacons.some((b) => b.op === "Drill"), "op label ('Drill') carried into the map");

console.log(`instrument self-test: ${ok ? "PASS" : "FAIL"}  (${map.total_beacons} beacons, est ${map.total_est_time_s}s)`);
process.exit(ok ? 0 : 1);
