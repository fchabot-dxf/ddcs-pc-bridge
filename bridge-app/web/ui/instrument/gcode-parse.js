// gcode-parse.js — G-code scanning for the browser instrumenter (JS port of checkpoint_insert.py's
// scan/strip_comment/op_label). Pure functions, no DOM. The Python self-test is the spec.

const WORD = /([A-Za-z])\s*([-+]?\d*\.?\d+)/g;

// Blank out DDCS comments: '(...)' spans and ';' to end-of-line. Enough for word extraction.
export function stripComment(line) {
  const out = [];
  let depth = 0;
  for (const ch of line) {
    if (depth === 0 && ch === ";") break;
    if (ch === "(") { depth++; out.push(" "); }
    else if (ch === ")") { depth = Math.max(0, depth - 1); out.push(" "); }
    else out.push(depth ? " " : ch);
  }
  return out.join("");
}

// If a line is essentially just a '(...)' comment (a CAM op header), return its text.
export function opLabel(line) {
  const m = line.match(/\(([^()]*)\)/);
  if (m && !stripComment(line).trim()) return m[1].trim();
  return null;
}

// One forward pass: track modal motion/pos/feed, per-move time, Z-up flag, current op label.
// Returns { moves: [{idx, cumT, zup, op}], totalTime }.
export function scan(lines, { rapid = 6000, defaultFeed = 1000, zupEps = 1e-4 } = {}) {
  let x = 0, y = 0, z = 0, have = false, feed = 0, mode = null, curOp = null, cum = 0;
  const moves = [];
  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const lab = opLabel(raw);
    if (lab !== null) curOp = lab;
    const code = stripComment(raw);
    const words = [...code.matchAll(WORD)];
    if (!words.length) continue;
    let nx = x, ny = y, nz = z, saw = false;
    for (const [, letter, val] of words) {
      const u = letter.toUpperCase();
      const v = parseFloat(val);
      if (u === "G" && [0, 1, 2, 3].includes(v)) mode = v | 0;
      else if (u === "X") { nx = v; saw = true; }
      else if (u === "Y") { ny = v; saw = true; }
      else if (u === "Z") { nz = v; saw = true; }
      else if (u === "F") feed = v;
    }
    if (!saw || mode === null) { x = nx; y = ny; z = nz; continue; }
    if (!have) { x = nx; y = ny; z = nz; have = true; continue; }
    const dist = Math.sqrt((nx - x) ** 2 + (ny - y) ** 2 + (nz - z) ** 2);
    const rate = mode === 0 ? rapid : (feed > 0 ? feed : defaultFeed);
    cum += rate > 0 ? (dist / rate) * 60.0 : 0;
    moves.push({ idx: i, cumT: cum, zup: (nz - z) > zupEps, op: curOp });
    x = nx; y = ny; z = nz;
  }
  return { moves, totalTime: cum };
}
