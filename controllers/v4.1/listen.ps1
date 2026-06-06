# listen.ps1 - auto baud-sweep serial boot-console capture.
# Just run it (no arguments). It steps through 9600..115200; power-cycle the controller
# each time it says to. At the end it tells you which baud caught readable text.
#   powershell -NoProfile -ExecutionPolicy Bypass -File listen.ps1
param([int]$Seconds = 12, [string]$Port = "COM4")
$bauds = 9600,19200,38400,57600,115200
$summary = [ordered]@{}
foreach ($baud in $bauds) {
    Write-Host ""
    Write-Host "================  BAUD $baud  ================" -ForegroundColor Cyan
    Write-Host ">>> POWER-CYCLE THE CONTROLLER NOW (off ~3s, then ON). Capturing ${Seconds}s..." -ForegroundColor Yellow
    try { $p = New-Object System.IO.Ports.SerialPort($Port,$baud,'None',8,'One'); $p.ReadTimeout = 300; $p.Open(); $p.DiscardInBuffer() }
    catch { Write-Host "  port open failed: $($_.Exception.Message)"; continue }
    $buf = New-Object System.Collections.Generic.List[byte]
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) { try { $b = $p.ReadByte(); if ($b -ge 0) { $buf.Add([byte]$b) } } catch {} }
    $p.Close()
    $bytes = $buf.ToArray()
    $printable = ($bytes | Where-Object { ($_ -ge 32 -and $_ -le 126) -or $_ -in 9,10,13 }).Count
    $summary[$baud] = "$($bytes.Count) bytes, $printable printable"
    Write-Host "  captured $($bytes.Count) bytes ($printable printable)"
    if ($printable -ge 8) {
        Write-Host "  *** LOOKS LIKE REAL TEXT @ $baud ***" -ForegroundColor Green
        Write-Host ([System.Text.Encoding]::ASCII.GetString($bytes) -replace '[^\x09\x0A\x0D\x20-\x7E]','.')
        [IO.File]::WriteAllBytes((Join-Path $env:TEMP "serial_$baud.bin"), $bytes)
    }
}
Write-Host "`n=================  SUMMARY  =================" -ForegroundColor Cyan
foreach ($k in $summary.Keys) { Write-Host ("  {0,-7}: {1}" -f $k, $summary[$k]) }
Write-Host "The baud with LOTS of printable bytes = the console. If all are ~0-2 bytes, there's no console on this pin."
