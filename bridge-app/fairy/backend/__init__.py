"""backend/ — the transport seam (ARCHITECTURE.md §4, PROTOCOL §3).

The Poller/Tracker are backend-agnostic: they only ever call these four methods.
`local_folder` is for testing the whole pipeline on one PC; `r2` is production.
Swapping between them is the entire "cloud vs local" switch.

No bucket retention. Every job's inbox/<jobId>.* is DELETED on delivery — the file then lives on
the controller's CNCDISK (which is where a same-session re-run comes from anyway; days later the
operator regenerates). Only status/<jobId>.json (metadata, no G-code) remains, for the tracker.

Two job types, keyed off the map (PROTOCOL §3/§4) — the only difference is whether fairy watches beacons:
  * TRACKED (has a .map.json, e.g. a Fusion cut): deliver -> watch beacons -> progress.
  * DELIVER-ONLY (no map, e.g. a probe / utility .nc): deliver -> "delivered" (terminal), no watch.
"""
from abc import ABC, abstractmethod


class Backend(ABC):
    @abstractmethod
    def list_inbox(self) -> list:
        """Return jobIds in inbox/, sorted ascending (== FIFO creation order)."""

    @abstractmethod
    def get_job(self, job_id: str):
        """Return (nc_bytes, map_dict) for a jobId. map_dict is {} if no map present."""

    @abstractmethod
    def put_status(self, job_id: str, status: dict) -> None:
        """Write status/<jobId>.json (PROTOCOL §5)."""

    @abstractmethod
    def delete_job(self, job_id: str) -> None:
        """Delete inbox/<jobId>.{nc,map.json} after delivery (every job — no retention; the file
        now lives on the controller). Removing it from inbox/ also keeps fairy from re-running it."""

    # --- CNCDISK file explorer (fairy publishes; web reads + issues delete commands) ---------
    @abstractmethod
    def put_cncdisk_index(self, index: dict) -> None:
        """Write cncdisk/index.json — fairy's listing of the controller's CNCDISK (PROTOCOL §7)."""

    @abstractmethod
    def list_commands(self) -> list:
        """Return pending [(cmdId, command_dict)] from commands/, sorted (FIFO)."""

    @abstractmethod
    def clear_command(self, cmd_id: str) -> None:
        """Delete commands/<cmdId>.json once fairy has processed it."""


def make_backend(config):
    if config.backend == "local":
        from .local_folder import LocalFolderBackend
        return LocalFolderBackend(config.local_root)
    if config.backend == "r2":
        from .r2 import R2Backend
        return R2Backend(config)
    raise ValueError(f"unknown backend: {config.backend!r} (expected 'local' or 'r2')")
