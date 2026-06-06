# CLAUDE.md

**Read [`AGENTS.md`](AGENTS.md) first.** It is the canonical entry point for this repo.

Critical reminder, repeated here because it is the easiest mistake to make:

> This repo covers **two different controllers** — the **DDCS V4.1** (bench sandbox @ `10.0.0.50`)
> and the **DDCS Expert / M350** (the real target). **They behave differently.** Never apply a
> finding from one to the other without checking [`controllers/README.md`](controllers/README.md).

Record new findings under the correct controller's `FINDINGS.md` with a confidence tag
(`[CONFIRMED]` / `[TO TEST]` / `[HYPOTHESIS]`).

For DDCS G-code / macro questions, consult the installed **`ddcs-expert`** skill (reference only).
