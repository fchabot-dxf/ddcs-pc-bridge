#!/usr/bin/env python3
r"""
DDCS Expert bridge ORCHESTRATOR (PC side).

Ties together the two proven-safe primitives from 2026-06-06:
  * SMB write to CNCDISK (push a G-code job to the controller)
  * Modbus RTU slave on COM6 (receive checkpoint sentinels the job pushes via MSETDATA)

It does three things:
  1. INSTRUMENT  - inject checkpoint pushes into a plain .nc at `(CKPT ...)` markers
                   (auto start + done sentinels too), so any job becomes trackable.
  2. PUSH        - copy the instrumented job to \\<ip>\CNCDISK over SMB.
  3. WATCH       - run the Modbus slave, decode incoming checkpoint frames, and report
                   live progress: which checkpoint was reached, DONE, or STALLED.

The operator still SELECTs + STARTs the job on the panel (remote start = a later
sysstart-dispatcher piece). This orchestrator gives the readback the bridge exists for:
the last checkpoint received = how far the job got before any stop/error.

SAFE BY DESIGN: only the checkpoint pattern proven on the machine (set an ordinary user
var, MSETDATA it). It never reads executor internals like #1630 (those wedge the analyzer).

Checkpoint wire format (matches CHECKPOINT_TEST.nc):
  HOLDING register 0 = (#251 << 8) | #250  where #251 = MARKER (job tag), #250 = checkpoint id.
  ids: 1..253 = user checkpoints, 254 = DONE (reached M30).

Requires pymodbus==3.6.9 (classic datastore). Run WATCH/PUSH from one process.

Examples:
  python orchestrator.py --self-test                         # offline: verify instrument+decode
  python orchestrator.py instrument job.nc -o job.instr.nc    # offline: write instrumented job
  python orchestrator.py run job.nc --port COM6 --ip 192.168.0.99   # instrument+push+watch
"""
import argparse
import os
import queue
import shutil
import threading
import time

MARKER = 111          # high byte tag identifying our checkpoint frames (#251)
DONE = 254            # checkpoint id meaning "reached M30 / finished"
MSET = "MSETDATA[250,1,0,2,16,300]"   # push #250/#251 -> HOLDING reg 0 (proven args)


# --------------------------------------------------------------------------- instrument
def instrument(lines, marker=MARKER):
    """Inject checkpoint pushes. A line containing '(CKPT' (optionally '(CKPT label)') becomes
    a checkpoint; we also add a start checkpoint and a DONE sentinel before the final M30.
    Returns (out_lines, labels) where labels maps id -> label text."""
    out = ["(instrumented by orchestrator.py)", f"#251 = {marker}"]
    labels = {}
    nid = 0

    def emit_ckpt(label):
        nonlocal nid
        nid += 1
        labels[nid] = label
        out.append(f"(CKPT {nid}: {label})")
        out.append(f"#250 = {nid}")
        out.append(MSET)

    emit_ckpt("start")
    saw_m30 = False
    for raw in lines:
        line = raw.rstrip("\n")
        stripped = line.strip()
        upper = stripped.upper()
        # A user checkpoint marker: (CKPT) or (CKPT some label)
        if upper.startswith("(CKPT"):
            label = stripped[5:].strip(" )") or f"ckpt{nid + 1}"
            emit_ckpt(label)
            continue
        # Final program end: drop a DONE sentinel just before it
        if upper == "M30" or upper.startswith("M30 ") or upper == "M02" or upper == "M2":
            out.append(f"#250 = {DONE}")
            out.append(MSET)
            out.append(line)
            saw_m30 = True
            continue
        out.append(line)
    if not saw_m30:
        out.append(f"#250 = {DONE}")
        out.append(MSET)
        out.append("M30")
    return out, labels


# --------------------------------------------------------------------------- modbus watch
def _make_slave_thread(port, baud, slave_id, evq):
    """Start a pymodbus RTU slave in a daemon thread; push (ts, addr, values) on register writes."""
    from pymodbus.datastore import (
        ModbusSequentialDataBlock, ModbusServerContext, ModbusSlaveContext)
    from pymodbus.server import StartSerialServer
    from pymodbus.transaction import ModbusRtuFramer

    class Block(ModbusSequentialDataBlock):
        def __init__(self):
            super().__init__(0, [0] * 2001)

        def setValues(self, address, values):
            super().setValues(address, values)
            vlist = values if isinstance(values, (list, tuple)) else [values]
            evq.put((time.time(), address, list(vlist)))

    store = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, [0] * 2001),
        co=ModbusSequentialDataBlock(0, [0] * 2001),
        hr=Block(), ir=Block(), zero_mode=True)
    context = ModbusServerContext(slaves={slave_id: store}, single=False)

    def _run():
        StartSerialServer(context=context, framer=ModbusRtuFramer, port=port,
                          baudrate=baud, bytesize=8, parity="N", stopbits=1)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


def watch(evq, labels, total, marker=MARKER, stall_timeout=40.0):
    """Consume checkpoint events; report progress; return when DONE or stalled."""
    last = None
    started = time.time()
    print(f"\nWatching for checkpoints (marker={marker}, expecting up to {total} + DONE). "
          f"Stall timeout {stall_timeout:.0f}s.\n")
    while True:
        try:
            ts, addr, vals = evq.get(timeout=stall_timeout)
        except queue.Empty:
            if last is None:
                print(f"[{_clk()}] STALLED: no checkpoints at all — job never ran? "
                      f"(syntax error → no frames + no .pos)")
            else:
                lab = labels.get(last, "?")
                print(f"[{_clk()}] STALLED after checkpoint {last} ({lab}) — job stopped there.")
            return {"status": "stalled", "last": last}
        for v in vals:
            if (v >> 8) != marker:
                continue  # not one of our checkpoint frames
            cid = v & 0xFF
            if cid == DONE:
                print(f"[{_clk()}] ✓ DONE — job finished cleanly "
                      f"(reached M30, {time.time() - started:.1f}s).")
                return {"status": "done", "last": last}
            last = cid
            lab = labels.get(cid, "?")
            print(f"[{_clk()}] ✓ checkpoint {cid} ({lab})")


def _clk():
    return time.strftime("%H:%M:%S")


# --------------------------------------------------------------------------- push
def push_smb(local_path, ip, name=None):
    name = name or os.path.basename(local_path)
    dest = rf"\\{ip}\CNCDISK\{name}"
    shutil.copyfile(local_path, dest)
    return dest


# --------------------------------------------------------------------------- self-test
def self_test():
    job = [
        "(demo job)", "G90", "(CKPT setup)", "G0 X0 Y0",
        "(CKPT roughing)", "G1 X10 F500", "M30",
    ]
    out, labels = instrument(job)
    text = "\n".join(out)
    assert "#251 = 111" in text, "marker not set"
    assert out.count(MSET) == 4, f"expected 4 pushes (start+2+done), got {out.count(MSET)}"
    assert f"#250 = {DONE}" in text and out.index(f"#250 = {DONE}") < out.index("M30"), "DONE before M30"
    assert labels[1] == "start" and labels[2] == "setup" and labels[3] == "roughing"
    # decode round-trip: reg = marker<<8 | id
    for cid in (1, 2, 3, DONE):
        reg = (MARKER << 8) | cid
        assert (reg >> 8) == MARKER and (reg & 0xFF) == cid
    print("self-test OK:")
    print(f"  checkpoints: {labels}")
    print(f"  pushes injected: {out.count(MSET)} (start + 2 markers + DONE)")
    print("  instrumented preview:")
    for ln in out:
        print("    " + ln)
    return 0


# --------------------------------------------------------------------------- cli
def main():
    ap = argparse.ArgumentParser(description="DDCS Expert bridge orchestrator")
    sub = ap.add_subparsers(dest="cmd")

    ap.add_argument("--self-test", action="store_true", help="run offline logic checks and exit")

    p_inst = sub.add_parser("instrument", help="write an instrumented copy of a job")
    p_inst.add_argument("job")
    p_inst.add_argument("-o", "--out", required=True)

    p_run = sub.add_parser("run", help="instrument + push + watch")
    p_run.add_argument("job")
    p_run.add_argument("--port", required=True)
    p_run.add_argument("--ip", required=True)
    p_run.add_argument("--baud", type=int, default=115200)
    p_run.add_argument("--slave", type=int, default=1)
    p_run.add_argument("--stall", type=float, default=40.0)
    p_run.add_argument("--name", default=None, help="filename on CNCDISK (default: job basename)")

    args = ap.parse_args()

    if args.self_test:
        return self_test()

    if args.cmd == "instrument":
        with open(args.job, "r", encoding="utf-8", errors="replace") as f:
            out, labels = instrument(f.readlines())
        with open(args.out, "w", encoding="ascii", errors="replace", newline="\r\n") as f:
            f.write("\n".join(out) + "\n")
        print(f"wrote {args.out}: {out.count(MSET)} checkpoint pushes; labels={labels}")
        return 0

    if args.cmd == "run":
        with open(args.job, "r", encoding="utf-8", errors="replace") as f:
            out, labels = instrument(f.readlines())
        instr_path = args.job + ".instr.nc"
        with open(instr_path, "w", encoding="ascii", errors="replace", newline="\r\n") as f:
            f.write("\n".join(out) + "\n")
        total = len(labels)
        evq = queue.Queue()
        _make_slave_thread(args.port, args.baud, args.slave, evq)
        time.sleep(1.0)
        name = args.name or (os.path.splitext(os.path.basename(args.job))[0] + ".nc")
        dest = push_smb(instr_path, args.ip, name)
        print(f"pushed instrumented job -> {dest}")
        print(f"checkpoints: {labels}")
        print(f"\n>>> On the panel: SELECT + START '{name}', then watch below.\n")
        result = watch(evq, labels, total, stall_timeout=args.stall)
        print(f"\nresult: {result}")
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
