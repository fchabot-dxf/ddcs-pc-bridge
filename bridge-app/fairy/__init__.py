"""fairy/ — the headless bridge on CNC-FAIRY (the only PC cabled to the DDCS Expert).

A loop: poll the rendezvous store -> write the .nc to the Expert (SMB) -> watch the
Modbus slave for beacons -> post progress back. Outbound-only; never internet-reachable.

See ../ARCHITECTURE.md (module map) and ../shared/PROTOCOL.md (the contract).
"""
