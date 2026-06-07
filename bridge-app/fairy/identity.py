"""identity.py — machine identity (CONFIGS §7).

The controller has no reliable unique ID over SMB, so identity is gateway-managed: we write a small
`.bridge-machine.json` onto the controller's disk, and verify it before every delivery so a job can
never land on the wrong controller. Identity lives on the controller's disk, so it travels with the
machine (survives a re-IP) and a swapped controller mismatches.

The file is read/written over the same path `transfer` delivers to (config.expert_dest), via plain
file ops — which work over the SMB UNC exactly as on a local folder (so it's testable offline).
"""
import json
import os
import uuid


def new_machine_id():
    return uuid.uuid4().hex


def _path(disk, filename):
    return os.path.join(disk, filename)


def read(disk, filename):
    """Return the identity dict from the controller, or None if absent/unreadable/unreachable."""
    try:
        with open(_path(disk, filename), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def provision(disk, filename, machine_id, name):
    """Write the identity file onto the controller's disk. Returns the written object."""
    obj = {"id": machine_id, "name": name}
    with open(_path(disk, filename), "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    return obj


def verify(disk, filename, expected_id):
    """(ok, reason). If no expected_id is configured, verification is skipped (ok=True) — first-run /
    unconfigured. Otherwise the controller's identity file must exist and match."""
    if not expected_id:
        return True, "unverified (no machine_id configured)"
    found = read(disk, filename)
    if found is None:
        return False, "no identity file on the controller (run provision)"
    if found.get("id") != expected_id:
        return False, f"machine mismatch: controller is {found.get('id')!r}, expected {expected_id!r}"
    return True, "ok"
