# Transport decision — Cloud-poll vs Token-endpoint

**Status:** proposed, for decision · **Date:** 2026-06-06 · **Scope:** how a job gets from the
**ASUS** (CAM/design laptop) to **CNC-FAIRY** (the only PC wired to the Expert), which then relays
it onto the controller. CNC-FAIRY→Expert is already solved (SMB over the private cable); this doc
is only about the **ASUS→CNC-FAIRY** hop.

## TL;DR
**Recommend Option A (cloud-poll).** For a machine that controls a spindle, the deciding factor is
attack surface, and cloud-poll keeps CNC-FAIRY **outbound-only / never internet-reachable**. The
token-endpoint's only real advantage is latency, which doesn't matter for file delivery. Both depend
on a third party and both work behind the guest NAT, so the token option mostly just *adds exposure*.
The choice is **reversible** — the relay uses a pluggable backend, so we can swap later.

## Context (the constraints we actually confirmed)
- The studio guest WiFi (`LImprimerie-Invite`) **isolates clients** — proven 2026-06-06: ASUS↔CNC-FAIRY
  ping + SMB(445) fail both ways even after opening CNC-FAIRY's firewall; ARP only resolves via the
  AP's proxy-ARP. So the two laptops **cannot talk on the LAN.** Both *do* have internet.
- It is **not our network** — no port-forwarding, no router config.
- **CNC-FAIRY is the only machine on the Expert's private cable** (`192.168.0.x`). The Expert's Samba is
  `security = share, guest = root` — wide open, no auth — so the controller **must stay isolated** and
  never be exposed to any shared or public network.
- The relay is a **plain deterministic script** (no AI, no decision-making) — poll, copy, count, report.
- **Operator presses Cycle Start** at the machine (remote Start unconfirmed). So nothing here cuts
  metal on its own; delivery is automatic, *running* is gated by a human. This is the safety backstop.

### Firm requirements (operator)
- **Queue.** Submit several jobs from the ASUS; they line up and deliver in order. CNC-FAIRY drains
  them one at a time.
- **Offline-tolerant.** If CNC-FAIRY is **asleep/off** when you submit, **waking it must auto-complete
  the pending transfers** — no manual step. (Requires the relay to auto-start on boot *and* on
  resume-from-sleep; CNC-FAIRY must actually wake — power/WoL/scheduled — since nothing runs while asleep.)

---

## Option A — Cloud-poll (Family 1)
ASUS uploads the instrumented job to a cloud folder/bucket; CNC-FAIRY's script **polls** that bucket,
pulls new jobs, writes them to the Expert, and posts progress back to the same bucket.

```
ASUS ──upload──▶ cloud bucket ◀──poll/pull── CNC-FAIRY ──SMB──▶ Expert
ASUS ◀──read──── status file  ◀──put──────── CNC-FAIRY (Modbus slave + map)
```

**The case for:**
- **No inbound exposure — the single biggest win.** CNC-FAIRY makes only *outbound* HTTPS calls.
  Nothing listens; there is no public URL; the machine that drives the CNC is **not reachable from the
  internet at all.** An attacker can't even find it. For spindle-control, this is the property that matters.
- **Works behind any hostile NAT/captive portal** with zero config — outbound 443 is always allowed.
- **Buffered / time-decoupled.** The cloud holds the job until CNC-FAIRY is ready. CNC-FAIRY can be
  asleep/off when you submit; it pulls the job when it wakes. The ASUS never has to "catch" it live.
- **One channel both ways** — progress rides back through the same bucket; no second mechanism.
- **Free audit trail** — the bucket is a natural history of every job sent.

**The case against:**
- **Polling latency** — delivery and progress lag by the poll interval (seconds). Irrelevant for file
  delivery; for live progress you just poll faster while a job is running.
- **Third-party data custody** — your G-code transits a cloud provider (briefly). A privacy/IP note for
  proprietary designs; mitigate by deleting after pickup, or a provider you trust.
- **A cloud key lives on CNC-FAIRY** — if stolen, an attacker can read/write your *bucket* — but still
  **cannot reach CNC-FAIRY** (no inbound path). Blast radius is the bucket, not the machine.
- Slightly more code than a raw socket (auth + list/get/put), but SDKs make it small.

---

## Option B — Token-endpoint + tunnel (Family 2)
CNC-FAIRY runs a small token-authenticated HTTP server, fronted by an **outbound tunnel**
(Cloudflare Tunnel / ngrok) that publishes a public HTTPS URL. The ASUS POSTs jobs to that URL.

```
ASUS ──POST (token)──▶ public URL ──tunnel──▶ CNC-FAIRY server ──SMB──▶ Expert
```

**The case for:**
- **Instant, event-driven** — the POST arrives and the relay writes to the Expert immediately. No poll
  delay; progress can *stream* (SSE/websocket) for a snappy live bar.
- **Real API** — submit / status / cancel / list as proper endpoints; cleaner programmatic control if
  you later want more than "drop a file."
- **TLS end-to-end** to the origin (with Cloudflare Tunnel); NAT handled by the outbound `cloudflared`.

**The case against:**
- **It puts the CNC on the internet.** Even token-guarded, there is now a public endpoint that routes
  to the machine controlling a spindle. The token is the *only* gate. A server bug, a leaked token, or a
  tunnel misconfig = someone can push G-code to your machine. This is a categorically larger risk than
  "outbound-only," and it's the whole reason to hesitate.
- **More moving parts to keep alive and secure** — the HTTP server *and* the `cloudflared` daemon *and*
  a public hostname/credentials. More to fail, monitor, and lock down.
- **Token lifecycle** — must be long, random, secret, rotated; a leak forces rotate + redeploy.
- **No buffering** — if CNC-FAIRY is off, the POST just fails; the ASUS must retry/hold. Tighter coupling.
- **Doesn't even escape third-party depend. ** `cloudflared`/ngrok *is* a cloud dependency — you trade a
  storage provider for a tunnel provider and **gain exposure** in the bargain.

---

## Head-to-head
| | A — Cloud-poll | B — Token-endpoint |
|---|---|---|
| CNC-FAIRY internet-reachable? | **No** (outbound only) | **Yes** (public URL) |
| Attack surface | minimal — nothing listens | a public endpoint to the CNC |
| Works behind guest NAT/captive portal | ✅ | ✅ (outbound tunnel) |
| Latency | seconds (poll) | instant |
| Buffers if CNC-FAIRY offline | ✅ holds in cloud | ❌ POST fails |
| Moving parts on CNC-FAIRY | 1 script | server + tunnel daemon |
| Third-party dependency | storage provider | tunnel provider (same class) |
| Secret on the machine | bucket key (blast radius = bucket) | token (blast radius = the machine) |
| Progress return | same channel | same connection (can stream) |

## The decision
The two are **equivalent** on the things people assume differ them (both beat the guest NAT, both lean on
a third party). They **differ** on exactly two axes:
1. **Exposure** — A is outbound-only; B publishes a path to the CNC. *Advantage A, and it's decisive for
   machine control.*
2. **Latency** — B is instant; A lags by the poll interval. *Advantage B, but it's worthless for "deliver
   a file," and A's faster-poll-during-run closes it for progress.*

When the asset on the far end **moves a spindle**, you trade a few seconds of latency for **never being
internet-reachable** every time. → **Choose A (cloud-poll).**

Pick B only if you later need a real-time, interactive, multi-client API exposed on purpose — which this
use case (one operator, file submit, human presses Start) does not.

## Reversibility & the middle path
- **Reversible:** the relay talks to a small backend interface (`get_job`, `put_status`, …). Cloud-poll is
  a `BucketBackend`; the token-endpoint would be an `HttpBackend`. Switching is filling in 4 functions —
  the relay logic, the instrumenter, and the progress decoder don't change.
- **If latency ever matters and exposure still mustn't:** **Tailscale** (private WireGuard mesh) gives
  near-instant, *private* (non-public) reachability through the isolation — the best-of-both, at the cost
  of a one-time install on both machines and another provider. Out of scope for now; noted as the upgrade.

## What is identical either way (not part of this decision)
Instrument-on-the-ASUS (`checkpoint_insert.py`, built ✅), the plain relay script on CNC-FAIRY, the Modbus
slave + checkpoint-map progress decode, the controller staying isolated on its cable, and the operator
pressing Start. The transport is the *only* thing this doc decides.
