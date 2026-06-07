# Deploying the cloud path (Phase 3)

**Cloud config** (CONFIGS.md): the **Console** runs on **Cloudflare Pages** (static `ui/` + Pages
**Functions** `functions/api/[[path]].js`), the **Gateway** polls **R2**. They never connect directly.
The browser never holds R2 keys — the Functions hold the R2 binding; the console authenticates to the
Functions with a shared **bearer token**.

```
 Console (Pages: ui/ + functions/api)  ──R2 binding──▶  R2 bucket  ◀──S3 (boto3)──  Gateway (fairy --backend r2)
   browser ── Bearer token ──▶ Functions
```

## 0. Prereqs (your Cloudflare account)
- R2 bucket **`ddcs-bridge`** (already created).
- **Gateway → R2:** an R2 **S3 API token** (R2 → *Manage R2 API Tokens* → Object Read & Write). Gives the
  **Account ID** (→ endpoint `https://<acct>.r2.cloudflarestorage.com`), **Access Key ID**, **Secret**.
- **Deploy:** `wrangler login` (with **Pages + R2**), or a `CLOUDFLARE_API_TOKEN` with Pages + R2 edit.

## 1. Verify R2 from the gateway side (proves the R2 backend)
```
set R2_ENDPOINT=https://<acct>.r2.cloudflarestorage.com
set R2_BUCKET=ddcs-bridge
set R2_ACCESS_KEY=<access key id>
set R2_SECRET_KEY=<secret>
cd bridge-app && python -m fairy.bridge --r2-check
```

## 2. Deploy the console (Pages + Functions)
One-time on the project: bind R2 + set the token —
- Dashboard: Pages project → Settings → Functions → **R2 binding `BUCKET` = `ddcs-bridge`**
- `wrangler pages secret put ACCESS_TOKEN`   (a long random string)
Then:
```
cd bridge-app/web
wrangler pages deploy ui --project-name ddcs-bridge
```
Open it once with the token (stored in the browser after):  `https://<proj>.pages.dev/?token=<ACCESS_TOKEN>`

## 3. Run the gateway in cloud mode (on CNC-FAIRY)
```
set R2_*  (the S3 token, as in step 1)
python -m fairy.bridge run --backend r2 --dest "\\192.168.0.99\CNCDISK" --port COM6 --machine-id <id> --name "<machine>"
```
It polls R2 `inbox/`+`commands/` and writes `status/`, `gateway/heartbeat.json`, `cncdisk/index.json`,
`history/`. Add `--serve` for a local zero-lag view at the machine too.

## Local smoke test (no cloud creds — emulated R2 via miniflare)
```
cd bridge-app/web && wrangler pages dev ui --r2 BUCKET
```
The console at the printed URL talks to the Functions backed by a local emulated R2 (submit/queue/
history/delete all work). This is how the cloud code was verified before deploy.

## Status
- [x] Pages Functions API + token auth + wrangler config — **built; verified locally on emulated R2.**
- [x] Console client: `?api=`/`?token=` + Authorization header; cloud connection status from the heartbeat.
- [ ] **Live:** `--r2-check`, `wrangler pages deploy`, end-to-end (console ↔ R2 ↔ gateway) — needs the creds above.
