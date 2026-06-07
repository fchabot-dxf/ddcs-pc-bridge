#!/usr/bin/env python3
r"""
checkpoint_insert.py - weave progress "beacons" into a CAM-generated DDCS Expert .nc job.

WHY: the Expert tells us NOTHING about where a running job is (no live line number is
readable over any safe channel - reading #1630 wedges the analyzer). So we make the JOB
report its own progress: at safe points it sets a counter var and MSETDATA-pushes it to a
PC Modbus slave. The slave counts beacons -> "62% . op 3 . line 3000/20000". This is the
proven-safe direction (MSETDATA push; CHECKPOINT_TEST.nc ran wedge-free on the machine
2026-06-06). MGETDATA (pull) is the one that hard-wedges - we never use it.

DESIGN (settled with the operator):
  * <= 255 beacons, counter in #250 (ONE byte, 1..255); #251 = 111 set once = frame marker.
    -> this is byte-for-byte the proven CHECKPOINT_TEST frame: MSETDATA[250,1,0,2,16,300].
  * Paced by ESTIMATED MACHINING TIME (every total_time/255), not by line count, so the
    percentage tracks wall-clock instead of jumping on long cuts.
  * Each beacon is PLACED on the next Z-up (safe retract / top-of-stock) move after its
    pacing mark - tool is clear of the work there, so the ~ms push can't disturb a cut.
  * A final "complete" beacon is forced just before M30 (so 100% == job finished clean).
  * Emits a JSON map (beacon# -> original line / op label / cum-time / percent) so the PC
    listener can translate a bare count back into line/op/percent/ETA.

It does NOT modify the source in place: writes <job>.bcn.nc + <job>.map.json.

Usage:
  python checkpoint_insert.py job.nc                 # -> job.bcn.nc + job.map.json
  python checkpoint_insert.py job.nc -o out.nc       # explicit instrumented output
  python checkpoint_insert.py job.nc --max 100       # cap beacons (default 255)
  python checkpoint_insert.py --self-test
"""
import json
import math
import re
import sys

# ---- knobs (all overridable on the CLI) -----------------------------------
VAR = 250                 # counter var (slot 150); proven safe in CHECKPOINT_TEST
MARKER_VAR = 251          # = 111, lets the slave recognise a checkpoint frame
MARKER = 111
MAX_BEACONS = 255         # one byte -> hard ceiling
RAPID_MM_MIN = 6000.0     # assumed G0 rate for time estimate (no accel model)
DEFAULT_FEED = 1000.0     # fallback if a cutting move has no modal F yet
ZUP_EPS = 1e-4            # Z must rise more than this to count as a retract

WORD = re.compile(r"([A-Za-z])\s*([-+]?\d*\.?\d+)")


def msetdata_call():
    # length 2 bytes -> packs #250(low)+#251(high) into holding reg 0; func 16 = write-multiple
    return f"MSETDATA[{VAR},1,0,2,16,300]"


def strip_comment(line):
    """Blank out DDCS comments: '(...)' spans and ';' to end-of-line. Good enough for word
    extraction (the linter does the strict nesting checks; here we just need the motion words)."""
    out = []
    depth = 0
    for ch in line:
        if depth == 0 and ch == ";":
            break
        if ch == "(":
            depth += 1
            out.append(" ")
        elif ch == ")":
            depth = max(0, depth - 1)
            out.append(" ")
        else:
            out.append(" " if depth else ch)
    return "".join(out)


def op_label(line):
    """Return a '(...)' comment's text if the line is essentially just a comment (CAM ops
    are emitted as '(2D Contour1)' header lines) - used as the human label for a beacon."""
    m = re.search(r"\(([^()]*)\)", line)
    if m and not strip_comment(line).strip():
        return m.group(1).strip()
    return None


class Move:
    __slots__ = ("idx", "cum_t", "zup", "op")

    def __init__(self, idx, cum_t, zup, op):
        self.idx, self.cum_t, self.zup, self.op = idx, cum_t, zup, op


def scan(lines):
    """One forward pass: track modal motion/pos/feed, compute per-move time, flag Z-up moves
    and the current op label. Returns (moves, total_time_seconds)."""
    x = y = z = 0.0
    have_pos = False
    feed = 0.0
    mode = None            # 0 rapid, 1 linear, 2/3 arc (arc time approximated by chord)
    cur_op = None
    moves = []
    cum = 0.0
    for i, raw in enumerate(lines):
        lab = op_label(raw)
        if lab is not None:
            cur_op = lab
        code = strip_comment(raw)
        words = WORD.findall(code)
        if not words:
            continue
        nx, ny, nz = x, y, z
        saw_axis = False
        for letter, val in words:
            u = letter.upper()
            v = float(val)
            if u == "G" and v in (0, 1, 2, 3):
                mode = int(v)
            elif u == "X":
                nx, saw_axis = v, True
            elif u == "Y":
                ny, saw_axis = v, True
            elif u == "Z":
                nz, saw_axis = v, True
            elif u == "F":
                feed = v
        if not saw_axis or mode is None:
            x, y, z = nx, ny, nz
            continue
        if not have_pos:
            # first positioned move: establish origin, don't bill travel-from-zero as cut time
            x, y, z, have_pos = nx, ny, nz, True
            continue
        dist = math.sqrt((nx - x) ** 2 + (ny - y) ** 2 + (nz - z) ** 2)
        rate = RAPID_MM_MIN if mode == 0 else (feed if feed > 0 else DEFAULT_FEED)
        cum += (dist / rate) * 60.0 if rate > 0 else 0.0
        zup = (nz - z) > ZUP_EPS
        moves.append(Move(i, cum, zup, cur_op))
        x, y, z = nx, ny, nz
    return moves, cum


def choose(moves, total_t, max_beacons):
    """Pick <= max_beacons Z-up moves, spaced ~evenly by estimated time."""
    zups = [m for m in moves if m.zup]
    if not zups or total_t <= 0:
        return zups[:max_beacons]
    step = total_t / max_beacons
    chosen = []
    nxt = step
    for m in zups:
        if m.cum_t >= nxt:
            chosen.append(m)
            while nxt <= m.cum_t:        # skip thresholds this retract already covers
                nxt += step
            if len(chosen) >= max_beacons:
                break
    return chosen


def find_m30(lines):
    for i, raw in enumerate(lines):
        if re.search(r"\bM30\b", strip_comment(raw)):
            return i
    return None


def instrument(text, max_beacons=MAX_BEACONS, source="job.nc"):
    lines = text.splitlines()
    moves, total_t = scan(lines)
    chosen = choose(moves, total_t, max_beacons - 1)   # reserve one for the forced M30 beacon

    # forced completion beacon just before M30 (guarantees a 100% signal)
    m30 = find_m30(lines)
    inserts = {}        # original-line-index -> list of (kind, op, cum_t)  (insert AFTER that line)
    beacons = []
    for m in chosen:
        inserts.setdefault(m.idx, []).append(("beacon", m.op, m.cum_t))
    if m30 is not None:
        # place the complete-beacon BEFORE the M30 line (i.e. after the line above it)
        inserts.setdefault(m30 - 1, []).append(("complete", chosen[-1].op if chosen else None, total_t))

    # emit
    out = []
    n = 0
    marker_done = False
    map_beacons = []
    first_beacon_line = chosen[0].idx if chosen else (m30 - 1 if m30 else None)
    for i, raw in enumerate(lines):
        if not marker_done and first_beacon_line is not None and i == first_beacon_line:
            out.append(f"#{MARKER_VAR} = {MARKER}")     # set the frame marker once, just in time
            marker_done = True
        out.append(raw)
        for kind, op, cum_t in inserts.get(i, []):
            n += 1
            out.append(f"#{VAR} = {n}")
            out.append(msetdata_call())
            map_beacons.append({
                "n": n,
                "orig_line": i + 1,                      # 1-based, into the SOURCE file
                "op": op,
                "cum_time_s": round(cum_t, 2),
                "percent": round(100.0 * cum_t / total_t, 1) if total_t > 0 else None,
                "complete": kind == "complete",
            })

    mapping = {
        "source": source,
        "var": VAR, "marker_var": MARKER_VAR, "marker": MARKER,
        "msetdata": msetdata_call(),
        "total_est_time_s": round(total_t, 2),
        "total_beacons": n,
        "beacons": map_beacons,
    }
    return "\n".join(out) + "\n", mapping


# --------------------------------------------------------------------------- self-test
def self_test():
    # synthetic job: 3 "operations", each a plunge + cut + RETRACT (Z-up). 4 retracts total
    # (3 op retracts + a final safe Z before M30). Feeds chosen so ops differ in time.
    job = "\n".join([
        "(Job header)",
        "G90 G54",
        "(2D Contour1)",
        "G0 X0 Y0 Z5",
        "G1 Z-1 F100",
        "G1 X50 F600",
        "G0 Z5",                # retract 1
        "(2D Contour2)",
        "G0 X0 Y10",
        "G1 Z-1 F100",
        "G1 X50 F600",
        "G0 Z5",                # retract 2
        "(Drill)",
        "G0 X0 Y20",
        "G1 Z-3 F50",
        "G0 Z5",                # retract 3
        "G0 Z25",               # final safe Z (also Z-up) before end
        "M30",
        "",
    ])
    out, mp = instrument(job, max_beacons=255, source="self-test")
    ok = True

    def check(cond, label):
        nonlocal ok
        print(f"  [{'ok' if cond else 'FAIL'}] {label}")
        ok = ok and cond

    # every beacon line is immediately preceded by a #250 assignment and followed by MSETDATA
    lines = out.splitlines()
    pushes = [i for i, l in enumerate(lines) if l.strip() == msetdata_call()]
    check(len(pushes) == mp["total_beacons"], f"push count == map beacons ({mp['total_beacons']})")
    check(all(lines[i - 1].strip().startswith(f"#{VAR} =") for i in pushes),
          "every MSETDATA is preceded by a #250 = n assignment")

    # marker set exactly once, before the first push
    markers = [i for i, l in enumerate(lines) if l.strip() == f"#{MARKER_VAR} = {MARKER}"]
    check(len(markers) == 1 and markers[0] < pushes[0], "marker #251=111 set once, before first push")

    # counter is 1..N strictly increasing, never exceeds 255
    nums = [int(lines[i - 1].split("=")[1]) for i in pushes]
    check(nums == list(range(1, len(nums) + 1)), "counter is 1..N strictly increasing")
    check(max(nums) <= 255, "counter never exceeds one byte (255)")

    # beacons only ever land right after a Z-up move (a 'G0 Z<higher>' in our synthetic job)
    src = job.splitlines()
    landed_ok = True
    for b in mp["beacons"]:
        if b["complete"]:
            continue
        srcline = src[b["orig_line"] - 1]
        landed_ok = landed_ok and ("Z5" in srcline or "Z25" in srcline) and "G0" in srcline
    check(landed_ok, "non-final beacons land on Z-up (retract) lines only")

    # a forced completion beacon exists and is the last one, ~100%
    last = mp["beacons"][-1]
    check(last["complete"] and last["percent"] in (100.0, None), "final beacon flagged complete at ~100%")

    # percent is monotonic non-decreasing
    pcts = [b["percent"] for b in mp["beacons"] if b["percent"] is not None]
    check(pcts == sorted(pcts), "percent is monotonic non-decreasing")

    # op labels carried through
    check(any(b["op"] == "Drill" for b in mp["beacons"]), "op label ('Drill') carried into the map")

    print("self-test:", "PASS" if ok else "FAIL")
    if ok:
        print(f"  ({mp['total_beacons']} beacons, est {mp['total_est_time_s']}s total)")
    return 0 if ok else 1


def main(argv):
    global VAR, MAX_BEACONS
    if "--self-test" in argv:
        return self_test()
    args, out_path, i = [], None, 0
    rest = argv[:]
    while rest:
        a = rest.pop(0)
        if a == "-o":
            out_path = rest.pop(0)
        elif a == "--max":
            MAX_BEACONS = int(rest.pop(0))
        elif a == "--var":
            VAR = int(rest.pop(0))
        elif not a.startswith("-"):
            args.append(a)
    if not args:
        print("usage: python checkpoint_insert.py <job.nc> [-o out.nc] [--max N] [--var 250]")
        print("       python checkpoint_insert.py --self-test")
        return 0
    src = args[0]
    with open(src, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    out, mp = instrument(text, MAX_BEACONS, source=src)
    base = src[:-3] if src.lower().endswith(".nc") else src
    out_path = out_path or base + ".bcn.nc"
    map_path = base + ".map.json"
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(mp, f, indent=2)
    print(f"{src}: {mp['total_beacons']} beacons, est {mp['total_est_time_s']}s")
    print(f"  -> {out_path}")
    print(f"  -> {map_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
