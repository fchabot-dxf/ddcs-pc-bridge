# Conformance corpus — DDCS Expert as parser oracle (PLANNED)

**Status: [PLANNED] — blocked on error-readback confirmation (see repo README "Current status").**

## Idea
DDCS-Studio's execution engine (`DDCS-Studio/ddcs-studio-modular/src/engine/`) emulates the
Expert's G-code/macro semantics. Today it is built from documented ground truth (ddcs-expert
skill + official Variables-ENG list). The wired bridge lets us replace "as-documented" with
"as-measured":

1. `corpus/` — tiny .nc probes, ONE parser behavior each. Every probe writes its observable
   result into user variables (#1100+) or a #1505 message.
2. Bridge delivers a probe, operator runs it, result returns via the completion-sentinel /
   run-state `.env` channel.
3. Each result lands twice:
   - `FINDINGS.md` entry tagged `[CONFIRMED]`
   - a fixture file replayed by the Studio engine's tests — engine output MUST match.

## First questions to ask the machine
- IF syntax: does the bare form (`IF #1922!=2 GOTO1`) parse, or only bracketed?
  (conditional-syntax-card.md has conflicting evidence)
- Empty G31 words (`G31 X#8 F#3 P#5 L Q`): error, or defaults?
- After a G31 MISS: exact value of #1920/#1921/#1922; does #1925-1927 keep the stale
  value from the previous probe?
- Unset #variable read: 0, or error?
- Nested parens inside ( comments ): accepted?
- Multi-digit GOTO labels; EQ/NE rejection.

## Rules
- Expert fixtures validate ONLY the Expert emulation. V4.1 results stay in v4.1/ (two-controller rule).
- Probes must be motion-free where possible (assignments + IF/GOTO + #1505) so they are safe
  to run unattended on the bench and the real machine alike.
