# listen.ps1 - LIVE serial listener (text appears as it arrives). One baud, long window.
# Usage:  powershell -NoProfile -ExecutionPolicy Bypass -File listen.ps1 [baud] [seconds] [port]
#   defaults: 115200, 60s, COM4
# How:  run it, then power-cycle the controller ONCE (off ~3s, on) whenever you like within the window.
#       Watch below - readable boot text means we found the console at that baud.
#       If you only see dots/garbage/nothing, stop (Ctrl+C) and re-run with a different baud:
#         listen.ps1 57600   |   listen.ps1 38400   |   listen.ps1 19200   |   listen.ps1 9600
param([int]$Baud = 115200, [int]$Seconds = 60, [string]$Port = "COM4")
$p = New-Object System.IO.Ports.SerialPort($Port, $Baud, 'None', 8, 'One')
$p.ReadTimeout = 200
$p.Open(); $p.DiscardInBuffer()
Write-Host "LIVE on $Port @ $Baud 8N1 for ${Seconds}s. Power-cycle the controller now (off ~3s, on)." -ForegroundColor Yellow
Write-Host "-------- output (text = console found; dots = non-printable) --------" -ForegroundColor Cyan
$all = New-Object System.Collections.Generic.List[byte]
$deadline = (Get-Date).AddSeconds($Seconds)
while ((Get-Date) -lt $deadline) {
    try { $b = $p.ReadByte() } catch { continue }
    if ($b -ge 0) {
        $all.Add([byte]$b)
        $ch = if (($b -ge 32 -and $b -le 126) -or $b -in 9,10,13) { [char]$b } else { '.' }
        Write-Host -NoNewline $ch
    }
}
$p.Close()
$printable = ($all | Where-Object { ($_ -ge 32 -and $_ -le 126) -or $_ -in 9,10,13 }).Count
Write-Host "`n-------- done: $($all.Count) bytes ($printable printable) @ $Baud --------" -ForegroundColor Cyan
[System.IO.File]::WriteAllBytes((Join-Path $env:TEMP "serial_$Baud.bin"), $all.ToArray())
