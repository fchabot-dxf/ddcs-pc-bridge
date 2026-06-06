# Claude Code Audio Feedback (this PC: RENDERRANCHY)

Lets Claude **ping the operator with sound** while they're looking away (e.g. at the CNC bench):
spoken TTS (Piper neural voices) + success/fail ringtones. All files live in `~/.claude/`
(`C:\Users\danse\.claude\`), so this applies to **every Claude Code session on this PC** (not the
studio laptops — those have their own `~/.claude`).

## How Claude triggers audio
| Want | Command |
|---|---|
| Speak a short alert | `powershell -NoProfile -ExecutionPolicy Bypass -File C:/Users/danse/.claude/say.ps1 "look back, I need input"` |
| Success ringtone | `... -File C:/Users/danse/.claude/chime.ps1 success` |
| Fail ringtone | `... -File C:/Users/danse/.claude/chime.ps1 fail` |

`say.ps1` auto-routes language: **English → Norman**, **French → Gilles** (accent/word detection).

## Files
- `say.ps1` — on-demand speak (any words). Works in any mode.
- `tts-speak.ps1` — shared `Invoke-Tts` core: Piper (UTF-8 piped for accents) + SAPI fallback.
- `tts-on-stop.ps1` — **Stop hook** script: auto-speaks Claude's reply per the mode below.
- `tts-mode.txt` — TTS mode: `1`/`all`, `2`/`last` (default), `3`/`trigger` (silent; on-demand only).
- `chime.ps1` — plays `sounds/<kind>.mp3|.wav` via MCI.
- `piper/` — `piper.exe` + voice models (`en_US-norman-medium.onnx`, `fr_FR-gilles-low.onnx`, others).
- `sounds/` — `success.mp3` (grunz, CC-BY), `fail.mp3` (JulyPink "Retro Game Fail", CC0), + WAV fallbacks.
- `freesound-token.txt` — freesound API key (rotate at https://freesound.org/apiv2/apply/ if needed).
- `freesound-get.ps1` — download a preview by ID: `... -File freesound-get.ps1 -Id <id> -OutName success.mp3`.

## TTS modes (edit `tts-mode.txt`)
- `1` / `all` — speak Claude's whole reply (markdown stripped).
- `2` / `last` — speak only Claude's last sentence. **(default)**
- `3` / `trigger` — silent automatically; Claude speaks only via `say.ps1`.

## Enabling auto-speak (modes 1/2) — MANUAL one-time step
Claude **cannot** edit `~/.claude/settings.json` (the safety classifier blocks self-modifying a file
that holds a broad permission rule). So add the Stop hook yourself: open **`/hooks`** → add a **Stop**
hook with command:
```
powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:/Users/danse/.claude/tts-on-stop.ps1
```
On-demand `say.ps1` / `chime.ps1` work **without** this hook.

## Changing sounds / voices
- **Swap a chime:** `freesound-get.ps1 -Id <freesoundId> -OutName success.mp3` (or `fail.mp3`).
- **Swap a voice:** download a model from HuggingFace `rhasspy/piper-voices` into `piper/`, then update
  the model path(s) in `tts-speak.ps1` (`Invoke-Tts`).

## Gotchas (why earlier attempts broke)
- **Scripts must be ASCII-only.** Windows PowerShell 5.1 reads `.ps1` as ANSI; literal accented chars
  or em-dashes mojibake and break parsing. Accents are detected by **code-point** (192..591), not
  literal chars.
- **Accents in spoken French** (ç, é…): PS 5.1's **native pipe** (`$msg | piper`) drops multibyte
  UTF-8 **even with `$OutputEncoding` set to UTF-8**. The reliable fix in `tts-speak.ps1`: write the
  text to a **UTF-8 (no-BOM) file** and feed Piper via **cmd's `< redirection`** (`cmd /c '"piper" …
  < text.txt'`). Don't revert to piping — that's what dropped the cédille.
- **Hook command paths use forward slashes** (`C:/Users/...`) — the hook runs through a bash shell
  (Git Bash present), which eats backslashes.
