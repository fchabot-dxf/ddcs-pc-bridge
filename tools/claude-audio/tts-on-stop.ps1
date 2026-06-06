# tts-on-stop.ps1 - Stop hook. Speaks Claude's reply per the mode in tts-mode.txt.
#   mode 1 / "all"     -> speak the whole reply (markdown stripped)
#   mode 2 / "last"    -> speak only the last sentence  (default)
#   mode 3 / "trigger" -> silent (on-demand only, via say.ps1)
$root = Join-Path $env:USERPROFILE ".claude"
$raw = [Console]::In.ReadToEnd()

$modeFile = Join-Path $root "tts-mode.txt"
$mode = if (Test-Path $modeFile) { (Get-Content $modeFile -Raw).Trim() } else { "2" }
if ($mode -eq "3" -or $mode -eq "trigger") { exit 0 }   # on-demand only

try { $data = $raw | ConvertFrom-Json } catch { exit 0 }
$tp = $data.transcript_path
if (-not $tp -or -not (Test-Path $tp)) { exit 0 }

# Find the last assistant message's text blocks.
$text = $null
$lines = Get-Content $tp
for ($i = $lines.Count - 1; $i -ge 0; $i--) {
    try { $o = $lines[$i] | ConvertFrom-Json } catch { continue }
    if ($o.type -eq "assistant" -and $o.message -and $o.message.content) {
        $parts = @()
        foreach ($c in $o.message.content) { if ($c.type -eq "text" -and $c.text) { $parts += $c.text } }
        if ($parts.Count -gt 0) { $text = ($parts -join " "); break }
    }
}
if (-not $text) { exit 0 }

# Strip markdown so it reads naturally.
$t = $text
$t = [regex]::Replace($t, '(?s)```.*?```', ' ')
$t = [regex]::Replace($t, '`[^`]*`', ' ')
$t = [regex]::Replace($t, '\[([^\]]+)\]\([^\)]+\)', '$1')
$t = [regex]::Replace($t, '[#>*_~|]', ' ')
$t = [regex]::Replace($t, '\s+', ' ').Trim()
if (-not $t) { exit 0 }

if ($mode -eq "2" -or $mode -eq "last") {
    $m = [regex]::Matches($t, '[^.!?]*[.!?]')
    if ($m.Count -gt 0) { $t = $m[$m.Count - 1].Value.Trim() }
}
if ($t.Length -gt 600) { $t = $t.Substring(0, 600) }

. (Join-Path $root "tts-speak.ps1")
Invoke-Tts $t
exit 0
