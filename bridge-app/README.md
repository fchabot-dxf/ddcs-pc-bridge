# bridge-app — DDCS Expert job bridge

Push a CNC job from anywhere, watch it run on the **DDCS Expert (M350)** — without exposing the
machine to the internet. This is the application the rest of the repo's findings were building toward.

> Targets the **Expert** specifically (uses Expert-only Modbus `MSETDATA` + the confirmed SMB write to
> CNCDISK). Not for the V4.1 bench. See [`../controllers/expert-m350/FINDINGS.md`](../controllers/expert-m350/FINDINGS.md).

## Two parallel apps, one bucket
The system is **two independent programs** that never talk directly — they rendezvous through a cloud
bucket (Cloudflare **R2**). That decoupling is what gives us a queue and "submit while CNC-FAIRY is
asleep, it auto-completes on wake."

```
   web/  ──writes jobs / reads status──▶  R2  ◀──reads jobs / writes status──  fairy/
   (Cloudflare app, the UI)            (bucket)                         (CNC-FAIRY, the hardware)
```

- **`web/`** — the centralized web app (Cloudflare Pages + Worker). Everything the operator touches:
  **send code · insert beacons · queue · live tracker.** Open from the ASUS, a phone, anywhere.
- **`fairy/`** — the headless bridge on CNC-FAIRY (the only PC cabled to the Expert). No UI. A loop:
  **poll R2 → write `.nc` to the Expert (SMB) → run the Modbus slave → post status to R2.** Outbound-only,
  never internet-reachable.
- **`shared/`** — [`PROTOCOL.md`](shared/PROTOCOL.md): the contract both apps obey (beacon frame, map
  schema, R2 bucket layout, job lifecycle). Read this first — it's the seam.

## Why this shape (decisions on record)
- Transport = **cloud-poll via R2**, chosen over an exposed token endpoint to keep the CNC machine
  un-exposed. Full argument: [`../TRANSPORT_DECISION.md`](../TRANSPORT_DECISION.md).
- The **transfer to the Expert is a plain SMB file copy** to `\\192.168.0.99\CNCDISK` (confirmed R/W
  2026-06-06). The cloud hop only gets bytes *to* CNC-FAIRY across the isolating guest WiFi.
- **Beacons** = `MSETDATA` progress pushes (proven wedge-free); the slave counts them → `%`, op, line, ETA.
  Reference implementation + spec: [`../controllers/expert-m350/tools/checkpoint_insert.py`](../controllers/expert-m350/tools/checkpoint_insert.py) (built, self-test passing).

## Safety (non-negotiable)
- **Delivery is automatic; running is not.** The file lands on the controller hands-free, but the
  **operator presses Cycle Start** at the machine. Remote auto-start is not confirmed — and is the gate.
- **No jog / no live motion control** here. That's a future, *separate*, local low-latency module with a
  hardware E-stop + watchdog (see [`../controllers/shared/ARCHITECTURE.md`](../controllers/shared/ARCHITECTURE.md)). This app is deliver + observe only.
- The controller stays **isolated** on its private cable; its wide-open `guest=root` SMB never touches a
  shared/public network.

## Status
- [x] Beacon instrumenter (Python reference, `checkpoint_insert.py`) — built, tested.
- [x] UI mockup ([`../controllers/expert-m350/tools/bridge_ui_mock.html`](../controllers/expert-m350/tools/bridge_ui_mock.html)) — open in a browser.
- [ ] `shared/PROTOCOL.md` — the contract (this scaffold).
- [ ] `fairy/` — bridge loop (Backend seam + LocalFolder backend first, then R2; reuse `modbus_slave.py`).
- [ ] `web/` — submit + beacon (browser) + queue + tracker, on R2.

## Build order
1. Lock `shared/PROTOCOL.md` (the seam).
2. `fairy/` against a **LocalFolder** backend → run instrument → "upload" → relay → tracker end-to-end here, no cloud account needed.
3. Swap in the **R2** backend.
4. `web/` (Pages + Worker), reusing the mockup as the frontend.
