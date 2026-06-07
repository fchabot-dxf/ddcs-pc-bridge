"""fairy/ — the headless bridge on CNC-FAIRY (the only PC cabled to the DDCS Expert).

A loop: poll the rendezvous store -> write the .nc to the Expert (SMB) -> watch the
Modbus slave for beacons -> post progress back. Outbound-only; never internet-reachable.

In offline/local configs it also serves the console + an operations API locally (see server.py).

See ../ARCHITECTURE.md (module map), ../CONFIGS.md (configs/vocab), ../shared/PROTOCOL.md (the contract).
"""

__version__ = "0.1.0"
