# chime.ps1 - play a success or fail ringtone. Usage: chime.ps1 success | chime.ps1 fail
# Plays sounds\<kind>.mp3 (preferred) or .wav via MCI (handles mp3 + wav).
param([string]$Kind = "success")
$dir = Join-Path $env:USERPROFILE ".claude\sounds"
$k = $Kind.ToLower()
$f = $null
foreach ($ext in ".mp3", ".wav") { $p = Join-Path $dir ($k + $ext); if (Test-Path $p) { $f = $p; break } }
if (-not $f) { return }
Add-Type -Name N -Namespace W -MemberDefinition '[DllImport("winmm.dll",CharSet=CharSet.Auto)] public static extern int mciSendString(string c, System.Text.StringBuilder r, int l, IntPtr h);'
[W.N]::mciSendString("close all", $null, 0, [IntPtr]::Zero) | Out-Null
[W.N]::mciSendString("open `"$f`" alias c", $null, 0, [IntPtr]::Zero) | Out-Null
[W.N]::mciSendString("play c wait", $null, 0, [IntPtr]::Zero) | Out-Null
[W.N]::mciSendString("close c", $null, 0, [IntPtr]::Zero) | Out-Null
