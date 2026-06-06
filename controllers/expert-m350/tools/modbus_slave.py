#!/usr/bin/env python3
"""
Modbus RTU SLAVE for the DDCS Expert (M350).

The Expert is the Modbus MASTER by default: it PUSHES status vars to us via
`MSETDATA` (a write) and PULLS commands from us via `MGETDATA` (a read). So the
PC must present a Modbus *slave* on the serial port the SABRENT FTDI cable lands on.

This slave logs every read/write the controller makes, across all four register
spaces. Per the RU manual, each controller var `#50..#499` carries exactly ONE byte
(decimal 0-255); MSETDATA byte-packs them two-per-register. X5 selects the Modbus
function (16 = write-multiple, 1 = read, etc.). So for register writes we print the
hi/lo BYTE split of each register (that's what maps back to #vars), not a float.

Wiring (port 2, via ferrule):  SABRENT TX(3)->RXD2(pin7)  RX(2)<-TXD2(pin8)  GND(5)<->GND(9)
Controller params:             #279 Modbus RTU = enable,  #267 Serial-2 baud = B115200,  #296/#297 => 8N1.  Reboot.

Requires pymodbus 3.6.x (classic datastore). Pinned: pip install "pymodbus==3.6.9"

Usage:
    python modbus_slave.py --port COM6 --baud 115200 --slave 1
    (find COM with:  python -c "import serial.tools.list_ports as p;[print(x.device,x.description) for x in p.comports()]")
"""
import argparse
import time

from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
    ModbusSlaveContext,
)
from pymodbus.server import StartSerialServer
from pymodbus.transaction import ModbusRtuFramer

SIZE = 2000  # registers/bits per space; covers any MSETDATA start address we expect


def _ts() -> str:
    return time.strftime("%H:%M:%S")


def _decode(values):
    """Each Modbus register = 2 bytes = 2 controller vars (1 byte each). Show the byte split
    both ways so we can match a frame back to the source #vars regardless of pack order."""
    hi = " ".join(f"{(v >> 8) & 0xFF},{v & 0xFF}" for v in values)   # hi-byte first
    lo = " ".join(f"{v & 0xFF},{(v >> 8) & 0xFF}" for v in values)   # lo-byte first
    return f"bytes[hi-first: {hi}] [lo-first: {lo}]"


class LoggingBlock(ModbusSequentialDataBlock):
    def __init__(self, name, numeric):
        self.name = name
        self.numeric = numeric  # holding/input -> show byte decodings
        super().__init__(0, [0] * (SIZE + 1))

    def setValues(self, address, values):
        super().setValues(address, values)
        vlist = values if isinstance(values, (list, tuple)) else [values]
        extra = f"   {_decode(vlist)}" if self.numeric and len(vlist) >= 1 else ""
        print(f"[{_ts()}] WRITE {self.name:<8} addr={address} n={len(vlist)} {list(vlist)}{extra}", flush=True)

    def getValues(self, address, count=1):
        v = super().getValues(address, count)
        print(f"[{_ts()}] READ  {self.name:<8} addr={address} count={count} -> {list(v)}", flush=True)
        return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True, help="COM port the SABRENT cable enumerates as (e.g. COM6)")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--slave", type=int, default=1, help="this slave's unit id (MSETDATA arg X2)")
    args = ap.parse_args()

    store = ModbusSlaveContext(
        di=LoggingBlock("DISCRETE", numeric=False),
        co=LoggingBlock("COIL", numeric=False),
        hr=LoggingBlock("HOLDING", numeric=True),
        ir=LoggingBlock("INPUT", numeric=True),
        zero_mode=True,  # request address N maps directly to block index N
    )
    context = ModbusServerContext(slaves={args.slave: store}, single=False)

    # Seed HOLDING regs 10..11 with a known pattern so an MGETDATA[...,10,4,3,...] read
    # returns recognizable bytes: addr10 -> #=55,66 ; addr11 -> #=77,88  (little-endian: reg=hi<<8|lo)
    store.setValues(3, 10, [(66 << 8) | 55, (88 << 8) | 77])  # fc=3 -> holding registers
    print(f"Modbus RTU slave up: {args.port} @ {args.baud} 8N1, unit id {args.slave}")
    print("Waiting for the controller (master) to MSETDATA/MGETDATA. Ctrl+C to stop.\n", flush=True)
    StartSerialServer(
        context=context,
        framer=ModbusRtuFramer,
        port=args.port,
        baudrate=args.baud,
        bytesize=8,
        parity="N",
        stopbits=1,
    )


if __name__ == "__main__":
    main()
