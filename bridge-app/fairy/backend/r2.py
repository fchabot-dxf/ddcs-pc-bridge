"""r2.py — the production backend: Cloudflare R2 over its S3-compatible API (boto3).

Same four methods as LocalFolderBackend; the Poller can't tell them apart. Outbound-only
HTTPS, so CNC-FAIRY stays un-exposed (TRANSPORT_DECISION.md, Option A).

[TO TEST] live against a real R2 bucket. The logic mirrors the local backend 1:1; only the
storage calls differ. Needs: pip install boto3, and R2_ENDPOINT/R2_BUCKET/R2_ACCESS_KEY/
R2_SECRET_KEY in the environment (config.from_env reads them).
"""
import json

from . import Backend

_INBOX = "inbox/"
_STATUS = "status/"
_CNCDISK_INDEX = "cncdisk/index.json"
_COMMANDS = "commands/"


class R2Backend(Backend):
    def __init__(self, config):
        import boto3  # lazy: only needed in production
        if not (config.r2_endpoint and config.r2_bucket):
            raise ValueError("R2 backend needs R2_ENDPOINT and R2_BUCKET (see config.from_env)")
        self.bucket = config.r2_bucket
        self.s3 = boto3.client(
            "s3",
            endpoint_url=config.r2_endpoint,
            aws_access_key_id=config.r2_access_key,
            aws_secret_access_key=config.r2_secret_key,
            region_name="auto",          # R2 ignores region but boto3 wants one
        )

    def list_inbox(self):
        ids = []
        token = None
        while True:
            kw = {"Bucket": self.bucket, "Prefix": _INBOX}
            if token:
                kw["ContinuationToken"] = token
            resp = self.s3.list_objects_v2(**kw)
            for o in resp.get("Contents", []):
                key = o["Key"]
                if key.endswith(".nc"):
                    ids.append(key[len(_INBOX):-3])
            if resp.get("IsTruncated"):
                token = resp.get("NextContinuationToken")
            else:
                break
        return sorted(ids)

    def get_job(self, job_id):
        nc = self.s3.get_object(Bucket=self.bucket, Key=f"{_INBOX}{job_id}.nc")["Body"].read()
        m = {}
        try:
            raw = self.s3.get_object(Bucket=self.bucket, Key=f"{_INBOX}{job_id}.map.json")["Body"].read()
            m = json.loads(raw)
        except self.s3.exceptions.NoSuchKey:
            pass
        return nc, m

    def put_status(self, job_id, status):
        self.s3.put_object(
            Bucket=self.bucket,
            Key=f"{_STATUS}{job_id}.json",
            Body=json.dumps(status, indent=2).encode("utf-8"),
            ContentType="application/json",
        )

    def delete_job(self, job_id):
        for ext in (".nc", ".map.json"):
            try:
                self.s3.delete_object(Bucket=self.bucket, Key=f"{_INBOX}{job_id}{ext}")
            except self.s3.exceptions.NoSuchKey:
                pass

    def put_cncdisk_index(self, index):
        self.s3.put_object(
            Bucket=self.bucket, Key=_CNCDISK_INDEX,
            Body=json.dumps(index, indent=2).encode("utf-8"), ContentType="application/json")

    def list_commands(self):
        out = []
        token = None
        while True:
            kw = {"Bucket": self.bucket, "Prefix": _COMMANDS}
            if token:
                kw["ContinuationToken"] = token
            resp = self.s3.list_objects_v2(**kw)
            for o in resp.get("Contents", []):
                key = o["Key"]
                if key.endswith(".json"):
                    raw = self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()
                    out.append((key[len(_COMMANDS):-5], json.loads(raw)))
            if resp.get("IsTruncated"):
                token = resp.get("NextContinuationToken")
            else:
                break
        return sorted(out, key=lambda c: c[0])

    def clear_command(self, cmd_id):
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=f"{_COMMANDS}{cmd_id}.json")
        except self.s3.exceptions.NoSuchKey:
            pass
