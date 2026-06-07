"""local_folder.py — the test backend. A root folder mirrors the R2 layout:
inbox/  status/. Lets the whole bridge run on one PC, no cloud account.
"""
import json
import os

from . import Backend


class LocalFolderBackend(Backend):
    def __init__(self, root):
        self.root = root
        self.inbox = os.path.join(root, "inbox")
        self.status = os.path.join(root, "status")
        self.cncdisk = os.path.join(root, "cncdisk")     # published listing lives here
        self.commands = os.path.join(root, "commands")
        for d in (self.inbox, self.status, self.cncdisk, self.commands):
            os.makedirs(d, exist_ok=True)

    def list_inbox(self):
        ids = [f[:-3] for f in os.listdir(self.inbox) if f.endswith(".nc")]
        return sorted(ids)

    def get_job(self, job_id):
        with open(os.path.join(self.inbox, job_id + ".nc"), "rb") as f:
            nc = f.read()
        m = {}
        map_path = os.path.join(self.inbox, job_id + ".map.json")
        if os.path.exists(map_path):
            with open(map_path, "r", encoding="utf-8") as f:
                m = json.load(f)
        return nc, m

    def put_status(self, job_id, status):
        path = os.path.join(self.status, job_id + ".json")
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(status, f, indent=2)
        os.replace(tmp, path)        # atomic — a reader never sees a half-written status

    def delete_job(self, job_id):
        for ext in (".nc", ".map.json"):
            path = os.path.join(self.inbox, job_id + ext)
            if os.path.exists(path):
                os.remove(path)

    def put_cncdisk_index(self, index):
        path = os.path.join(self.cncdisk, "index.json")
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2)
        os.replace(tmp, path)

    def list_commands(self):
        out = []
        for f in sorted(os.listdir(self.commands)):
            if f.endswith(".json"):
                with open(os.path.join(self.commands, f), encoding="utf-8") as fh:
                    out.append((f[:-5], json.load(fh)))
        return out

    def clear_command(self, cmd_id):
        path = os.path.join(self.commands, cmd_id + ".json")
        if os.path.exists(path):
            os.remove(path)
