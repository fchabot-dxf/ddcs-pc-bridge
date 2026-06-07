"""DDCS Bridge — desktop app (pywebview).

The gateway in a native window: one Python process — the gateway loop runs in a daemon thread and the
console shows in a WebView2 window (no browser, no separate server). Reads optional per-machine config
from ~/.ddcs-bridge/config.json. Bundle with PyInstaller -> one .exe (see web/DEPLOY.md / build).

Run from source:  cd bridge-app && python desktop.py
"""
import json
import os
import sys
import threading
import time

import webview

from fairy.bridge import run_loop
from fairy.config import Config

APP_DATA = os.path.join(os.path.expanduser("~"), ".ddcs-bridge")


def _bundle_dir():
    # PyInstaller unpacks data to sys._MEIPASS; from source it's this file's dir.
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def _overrides():
    """Optional ~/.ddcs-bridge/config.json — per-machine setup without rebuilding the exe. Keys:
    backend, dest, com_port, enable_slave, machine_id, machine_name, port, r2_* (for cloud)."""
    try:
        with open(os.path.join(APP_DATA, "config.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def build_config():
    ov = _overrides()
    return Config.from_env(
        backend=ov.get("backend", "local"),
        local_root=ov.get("local_root", os.path.join(APP_DATA, "data")),
        expert_dest=ov.get("dest", ""),                  # unconfigured until set in Setup (a network share)
        com_port=ov.get("com_port"),
        machine_id=ov.get("machine_id"),
        machine_name=ov.get("machine_name"),
        enable_slave=ov.get("enable_slave", False),      # default off (no Modbus) until configured
        serve=True, host="127.0.0.1", port=int(ov.get("port", 8765)),
        console_dir=os.path.join(_bundle_dir(), "web", "ui"),
        config_path=os.path.join(APP_DATA, "config.json"),   # Setup persists here
        open_browser=False,                              # the window IS the UI
    )


def main():
    cfg = build_config()
    threading.Thread(target=run_loop, args=(cfg,), daemon=True).start()

    url = f"http://{cfg.host}:{cfg.port}"
    import urllib.request
    for _ in range(80):                                  # wait for the local server to come up
        try:
            urllib.request.urlopen(url + "/api/descriptor", timeout=1)
            break
        except Exception:
            time.sleep(0.1)

    webview.create_window("DDCS Bridge", url, width=900, height=840)
    webview.start()


if __name__ == "__main__":
    main()
