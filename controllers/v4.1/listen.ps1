# listen.ps1 - auto baud-sweep, LIVE output, generous window per baud.
# Just run it (no args). For EACH baud it banners "POWER-CYCLE NOW", listens live for
# 30s, then auto-advances to the next baud. Power-cycle once per banner.
#   powershell -NoProfile -ExecutionPolicy Bypass -File listen.ps1
# (optional: listen.ps1 <secondsPerBaud> <port>)
param([int]$SecondsPerBaud = 30, [string]$Port = "COM4")
$bauds = 115200,57600,38400,19200,9600
$summary = [ordered]@{}
foreach ($baud in $bauds) {
    Write-Host "`n==================== BAUD $baud ====================" -ForegroundColor Cyan
    Write-Host "  >>>>>>  POWER-CYCLE THE CONTROLLER NOW  (off ~3s, then ON)  <<<<<<" -ForegroundColor Yellow
    Write-Host "  listening live for ${SecondsPerBaud}s, then auto-advancing... (Ctrl+C if you see real text)"
    try { $p = New-Object System.IO.Ports.SerialPort($Port,$baud,'None',8,'One'); $p.ReadTimeout = 200; $p.Open(); $p.DiscardInBuffer() }
    catch { Write-Host "  port open failed: $($_.Exception.Message)"; continue }
    $all = New-Object System.Collections.Generic.List[byte]
    $deadline = (Get-Date).AddSeconds($SecondsPerBaud)
    while ((Get-Date) -lt $deadline) {
        try { $b = $p.ReadByte() } catch { continue }
        if ($b -ge 0) {
            $all.Add([byte]$b)
            $ch = if (($b -ge 32 -and $b -le 126) -or $b -in 9,10,13) { [char]$b } else { '.' }
            Write-Host -NoNewline $ch
        }
    }
    $p.Close()
    $bytes = $all.ToArray()
    $pr = ($bytes | Where-Object { ($_ -ge 32 -and $_ -le 126) -or $_ -in 9,10,13 }).Count
    $summary[$baud] = "$($bytes.Count) bytes, $pr printable"
    Write-Host "`n  [baud $baud done: $($bytes.Count) bytes, $pr printable]"
    if ($pr -ge 8) {
        Write-Host "  *** REAL TEXT @ $baud  -- console likely found! ***" -ForegroundColor Green
        [System.IO.File]::WriteAllBytes((Join-Path $env:TEMP "serial_$baud.bin"), $bytes)
    }
}
Write-Host "`n==================== SUMMARY ====================" -ForegroundColor Cyan
foreach ($k in $summary.Keys) { Write-Host ("  {0,-7}: {1}" -f $k, $summary[$k]) }
Write-Host "Baud with lots of printable bytes = the console. All ~0-2 bytes = no console on this pin."
