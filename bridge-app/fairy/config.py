"""config.py — every knob in one place (ARCHITECTURE.md §4).

Defaults match the confirmed studio rig (COM6 @ 115200, Expert CNCDISK at 192.168.0.99).
R2 credentials are read from the environment so secrets never live in the repo.
"""
import os
from dataclasses import dataclass


@dataclass
class Config:
    # --- backend (the rendezvous store; PROTOCOL §3) -----------------------
    backend: str = "local"                  # "local" (test) | "r2" (prod)
    local_root: str = "./_bridge_data"      # local-folder backend root (inbox/ status/)

    # --- R2 (only used when backend == "r2"); pulled from env --------------
    r2_endpoint: str = ""
    r2_bucket: str = ""
    r2_access_key: str = ""
    r2_secret_key: str = ""

    # --- transfer to the controller (transfer.py — the only hardware path) -
    # The controller's CNCDISK network share, e.g. \\192.168.0.99\CNCDISK or \\10.0.0.50\cncdisk.
    # Empty = unconfigured (set it in the Setup UI). MUST be a network share — the Setup layer rejects
    # local folders so the connection is always a real controller (no confusing local "sandbox").
    expert_dest: str = ""

    # --- Modbus slave (slave.py) ------------------------------------------
    com_port: str = "COM6"                  # SABRENT FTDI on CNC-FAIRY
    baud: int = 115200
    slave_id: int = 1
    enable_slave: bool = True               # False (--no-slave): skip the Modbus slave (UI/SMB-only; no serial/pymodbus)

    # --- loop / timing ----------------------------------------------------
    poll_interval_s: float = 5.0            # while idle (no active job)
    run_poll_interval_s: float = 1.0        # while a job is active (faster progress)
    stall_seconds: float = 120.0            # no new beacon this long -> "stalled"

    cncdisk_refresh_s: float = 15.0         # how often to republish the CNCDISK file listing
    heartbeat_s: float = 20.0               # how often to publish the gateway heartbeat

    # --- machine identity (which controller this gateway serves; CONFIGS §7) -------
    machine_id: str = ""                    # expected controller id; empty = unconfigured (verify skipped)
    machine_name: str = ""                  # human label, e.g. "Ultimate Bee"
    identity_filename: str = ".bridge-machine.json"   # written on the controller's disk

    # --- local server (offline / local configs: serve the console + ops API) ------
    serve: bool = False                     # run the local HTTP server (server.py)
    host: str = "127.0.0.1"                 # bind address (0.0.0.0 to reach from the LAN)
    port: int = 8765
    console_dir: str = ""                   # static console files to serve at / (empty = none yet)
    open_browser: bool = False              # --open: pop the console in the default browser on start
    config_path: str = ""                   # where Setup persists config (empty -> ~/.ddcs-bridge/config.json)

    # --- WebSocket telemetry (Command Center broadcast; telemetry.py) --------------
    enable_ws: bool = False                 # --ws: start the WebSocket telemetry server
    ws_port: int = 8766                     # WebSocket bind port (separate from the HTTP port 8765)

    @classmethod
    def from_env(cls, **overrides):
        """Build a Config, layering env vars (for secrets) then explicit overrides."""
        c = cls()
        c.r2_endpoint = os.environ.get("R2_ENDPOINT", c.r2_endpoint)
        c.r2_bucket = os.environ.get("R2_BUCKET", c.r2_bucket)
        c.r2_access_key = os.environ.get("R2_ACCESS_KEY", c.r2_access_key)
        c.r2_secret_key = os.environ.get("R2_SECRET_KEY", c.r2_secret_key)
        for k, v in overrides.items():
            if v is not None:
                setattr(c, k, v)
        return c
