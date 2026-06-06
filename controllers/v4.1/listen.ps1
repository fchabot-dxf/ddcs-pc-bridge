# listen.ps1 - capture serial boot/console output, then you power-cycle.
# Usage (from PowerShell in this folder):
#   powershell -NoProfile -ExecutionPolicy Bypass -File listen.ps1 57600
#   powershell -NoProfile -ExecutionPolicy Bypass -File listen.ps1 38400 40
# Args: [baud] [seconds] [port]   (defaults: 115200, 30s, COM4)
# Order: RUN THIS FIRST, then power-cycle the controller while it's listening.
param([int]$Baud = 115200, [int]$Seconds = 30, [string]$Port = "COM4")
$p = New-Object System.IO.Ports.SerialPort($Port, $Baud, 'None', 8, 'One')
$p.ReadTimeout = 400
$p.Open(); $p.DiscardInBuffer()
Write-Host "Listening $Port @ $Baud 8N1 for ${Seconds}s  ==>  POWER-CYCLE THE CONTROLLER NOW (off ~3s, on)" -ForegroundColor Yellow
$buf = New-Object System.Collections.Generic.List[byte]
$deadline = (Get-Date).AddSeconds($Seconds)
while ((Get-Date) -lt $deadline) { try { $b = $p.ReadByte(); if ($b -ge 0) { $buf.Add([byte]$b) } } catch {} }
$p.Close()
$bytes = $buf.ToArray()
Write-Host "`ncaptured $($bytes.Count) bytes @ $Baud"
if ($bytes.Count -gt 0) {
  Write-Host "--- ASCII (printable; '.' = non-printable) ---"
  Write-Host ([System.Text.Encoding]::ASCII.GetString($bytes) -replace '[^\x09\x0A\x0D\x20-\x7E]','.')
  $out = Join-Path $env:TEMP ("serial_$Baud.bin"); [IO.File]::WriteAllBytes($out, $bytes)
  Write-Host "raw bytes saved: $out"
} else { Write-Host "(nothing at this baud - try a different one)" }
