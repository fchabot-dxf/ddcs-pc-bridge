# Claude Code Audio Feedback (tooling backup)

Version-controlled copy of the audio-feedback setup that lets Claude Code **ping the operator with
speech + success/fail chimes** while they're at the CNC bench. The *live* install is in `~/.claude/`
on **RENDERRANCHY**; this is the portable backup (deployable to the studio laptops).

**Not included here (by design):** the freesound API token (secret) and the large Piper voice models /
sound files (they're re-downloaded during setup).

## Files
- `say.ps1` — on-demand speak: `... -File say.ps1 "look back, I need you"`.
- `chime.ps1` — `chime.ps1 success` | `chime.ps1 fail`.
- `tts-speak.ps1` — shared `Invoke-Tts` (Piper EN=Norman / FR=Gilles, accents via cmd-redirection; SAPI male fallback).
- `tts-on-stop.ps1` — Stop-hook script (auto-speak per `tts-mode.txt`).
- `tts-mode.txt` — `1`/all · `2`/last (default) · `3`/trigger (silent).
- `freesound-get.ps1` — `freesound-get.ps1 -Id <id> -OutName success.mp3`.
- `AUDIO-FEEDBACK.md` — full reference + gotchas.

## Deploy on a new PC
1. Copy these files into `~/.claude/`.
2. **Piper:** download `piper_windows_amd64.zip` (GitHub `rhasspy/piper`) → `~/.claude/piper/`.
3. **Voices:** from HuggingFace `rhasspy/piper-voices` → `~/.claude/piper/`
   (`en_US-norman-medium`, `fr_FR-gilles-low`).
4. **Token:** save your freesound API key to `~/.claude/freesound-token.txt`.
5. **Chimes:** `freesound-get.ps1 -Id 109662 -OutName success.mp3` ; `-Id 848654 -OutName fail.mp3`.
6. **Auto-speak (optional):** add a Stop hook via `/hooks` → `tts-on-stop.ps1` (see AUDIO-FEEDBACK.md).

> Note: paths in the scripts are `C:/Users/danse/.claude/...` (RENDERRANCHY). Re-path for other machines.
