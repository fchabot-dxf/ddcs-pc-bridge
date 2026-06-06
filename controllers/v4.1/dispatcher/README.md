# V4.1 Software Dispatcher (M47 self-loop) — prototype

A PC-driven job dispatcher for the DDCS V4.1 over Ethernet, built on proven mechanics
(see [`../FINDINGS.md`](../FINDINGS.md)):
- an **`M47` loop re-reads its program file from disk every cycle** → commands travel in the file;
- **variables persist in RAM across cycles** → a run-once gate works;
- **`uservar` flushes RAM→file** → the PC reads results back over SMB.

**Bootstrap model:** one manual **Start** launches the loop (operator-accepted; the Expert's
`sysstart.nc` would make even that automatic). Thereafter the PC drives everything over Ethernet.

## Files
- [`ddcs-dispatch.ps1`](ddcs-dispatch.ps1) — PC orchestrator: `Initialize-Dispatcher`, `Send-DdcsJob`,
  `Wait-DdcsJob`, `Get-DdcsStatus`.

## Protocol (variables in `uservar` readback range)
| #var | slot | role |
|---|---|---|
| `#240` | 140 | command id — set by the **file literal** each cycle (the inbound channel) |
| `#241` | 141 | last-done id — **RAM gate** (persists across cycles) → run-once |
| `#243` | 143 | started-id sentinel (readback) |
| `#244` | 144 | done-id sentinel (readback) |
| `#246` | 146 | heartbeat / cycle counter (loop-alive + rate) |

Per cycle the loop: bump `#246`; set `#240` from the file literal; if `#240==#241` skip to idle;
else mark started (`#243`), run the injected job, mark done (`#244`), set `#241=#240`. Idle `G4`+`M47`.

**Run-once:** the PC bumps the id for each job; a job runs the one cycle where `#240 != #241`.
**Atomic write:** the PC writes a temp file then **renames** it into place, so the fast loop never
reads a torn/half-written file.

## ⚠️ Known limitation — a bad job halts the loop
A **syntax/parse error in a job halts the entire loop** (no `error.nc` on V4.1, no G-code try/catch).
The orchestrator detects it (`#243==id` but `#244` never reaches it = "job id errored, loop dead"),
but recovery needs the loop relaunched (a Start). Mitigation is layered:
1. **PC pre-lint** jobs before sending → makes halts rare (imperfect vs. the quirky parser, but
   catches most). `[TO BUILD]`
2. **Auto re-trigger** for the rare halt — press **Start** without a human:
   - **Serial "Start" key** — the dispatcher reduces serial to **one key** (no navigation). Success is
     **auto-detectable over SMB** (watch `#246` resume incrementing). Prereq: verify port-1 voltage
     first (don't fry a TTL input with RS-232). `[TO TEST]`
   - **External Start input** — contact closure via relay/optocoupler/ESP32; no protocol, but needs IO
     wiring + mapping. `[TO TEST]`

Job bodies must **not** contain loop-breakers (`M0/M2/M30/M47/M98/M99`) or the protocol vars; the
orchestrator rejects those.

## Test plan (on the bench)
1. `Initialize-Dispatcher`; operator selects `DISPATCH.nc` + Start once.
2. `Get-DdcsStatus` → confirm `#246` heartbeat increments (loop alive); **measure rate** over ~10 s
   (the `G4 P200` pacing is unproven — if it spins very fast, address NAND-wear/CPU before leaving it
   running). `[TO TEST]`
3. `Send-DdcsJob "#250=4242"` → `Wait-DdcsJob` → expect DONE; confirm `#250` (slot 150) = 4242.
4. Send a **deliberately bad** job → expect `Wait-DdcsJob` = ERROR/STALLED and the heartbeat to stop
   (validates error detection + confirms the halt behavior).
5. Confirm the **atomic rename** never trips a torn read during rapid sends. `[TO TEST]`
