# say.ps1 - on-demand speak (works in any TTS mode; Claude calls this to grab your attention).
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File say.ps1 your message here
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Words)
. (Join-Path $env:USERPROFILE ".claude\tts-speak.ps1")
$msg = ($Words -join " ")
if (-not $msg.Trim()) { $msg = "Claude needs you." }
Invoke-Tts $msg
