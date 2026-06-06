# Archive — historical / superseded

The project's **original** planning docs, kept for history only. Later bench testing + firmware
analysis **corrected** many of their assumptions, so **do NOT treat these as current.**

**Current source of truth →** [`../controllers/README.md`](../controllers/README.md) (V4.1-vs-Expert
matrix + disambiguation rule), the per-controller `FINDINGS.md`,
[`../controllers/shared/ARCHITECTURE.md`](../controllers/shared/ARCHITECTURE.md), and
[`../controllers/v4.1/ETHERNET_TESTS.md`](../controllers/v4.1/ETHERNET_TESTS.md).

| Archived file | What it was | Superseded by |
|---|---|---|
| `DESIGN.md` | original architecture + early findings | `controllers/shared/ARCHITECTURE.md` + `controllers/*/FINDINGS.md` |
| `EXPERIMENTS.md` | original Track A–E experiment plan | `controllers/v4.1/ETHERNET_TESTS.md` + FINDINGS |
| `DDCS_RS232_probe_notes.md` | early serial-probe log (incl. the now-wrong "serial is receive-only / not the path" call) | `controllers/v4.1/FINDINGS.md` (Serial + Firmware internals) |
| `ddcs-homebrew-api.skill` | packaged snapshot of the old DESIGN/EXPERIMENTS | the live `controllers/` docs |

**Key corrections the archive predates** (now in the live docs):
- `error.nc` does **not** fire on software/syntax errors (V4.1) — it's a system-alarm hook.
- A free-running `M47` dispatcher **can't read back live** — vars flush only at run start/stop.
- `sysstart.nc` is **Expert-only** (V4.1 has none; its startup-ish file is `advstart.nc`).
- The **M3K serial protocol is kernel-level** — not in any app binary we have.
- Confirmed Expert RS232 pinout: **RXD1=2, TXD1=3, RXD2=7, TXD2=8, GND=5/9**; M3K = 115200.
