# ddcs-dispatch.ps1 — PC orchestrator for the V4.1 "M47 self-loop" software dispatcher.
#
# Proven mechanics this builds on (see ../FINDINGS.md):
#   - An M47 loop re-reads its program file from disk EVERY cycle  -> commands travel in the file.
#   - Variables persist in RAM across cycles                       -> run-once gate works.
#   - uservar flushes RAM->file                                    -> PC reads results back over SMB.
#
# Model: ONE manual Start bootstraps the loop; thereafter the PC drives everything over Ethernet.
#
# Usage (dot-source, then call):
#   . .\ddcs-dispatch.ps1 -Ip 10.0.0.50
#   Initialize-Dispatcher              # writes idle DISPATCH.nc; operator selects it + Start once
#   $id = Send-DdcsJob "#250=4242"     # push a job (any G-code WITHOUT loop-breakers); returns its id
#   Wait-DdcsJob $id                   # poll until DONE / ERROR / TIMEOUT
#   Get-DdcsStatus                     # heartbeat + protocol vars

param([string]$Ip = "10.0.0.50")

$script:Cnc      = "\\$Ip\cncdisk"
$script:Sys      = "\\$Ip\sysdisk"
$script:DispName = "DISPATCH.nc"
$script:DispPath = "$script:Cnc\$script:DispName"
$script:TmpPath  = "$script:Cnc\DISPATCH.tmp"
$script:Uservar  = "$script:Sys\uservar"
$script:IdFile   = Join-Path $env:TEMP "ddcs_dispatch_lastid.txt"

# protocol variables (#var); all in uservar readback range #100-#499 (slots 140-146)
$script:V_CMD = 240   # command id   (set by the file literal each cycle)
$script:V_LAST= 241   # last-done id (RAM gate; persists across cycles -> run-once)
$script:V_START=243   # started-id sentinel
$script:V_DONE =244   # done-id sentinel
$script:V_HB  = 246   # heartbeat / cycle counter

function Connect-Ddcs { cmd /c "net use \\$Ip\IPC`$ /user:guest `"`"" 2>$null | Out-Null }

function Read-DdcsVar([int]$v) {
    $b = [System.IO.File]::ReadAllBytes($script:Uservar)
    [System.BitConverter]::ToDouble($b, ($v - 100) * 8)
}

# Build the dispatcher program text. V4.1 macro syntax: no spaces in assigns/IF, no space before GOTO.
function Build-Dispatcher([int]$id, [string]$job) {
@"
(DDCS DISPATCHER cmd $id)
#$($script:V_HB)=#$($script:V_HB)+1
#$($script:V_CMD)=$id
IF#$($script:V_CMD)==#$($script:V_LAST)GOTO90
#$($script:V_START)=#$($script:V_CMD)
#$($script:V_DONE)=0
$job
#$($script:V_DONE)=#$($script:V_CMD)
#$($script:V_LAST)=#$($script:V_CMD)
N90
G4 P200
M47
"@
}

# Reject job bodies that would break the loop or clobber protocol vars.
function Test-JobSafe([string]$job) {
    if ($job -match '(?im)\bM0*(0|2|30|47|98|99)\b') {
        throw "Job must NOT contain M0/M2/M30/M47/M98/M99 (they would end/break the dispatcher loop)."
    }
    foreach ($pv in $script:V_CMD,$script:V_LAST,$script:V_START,$script:V_DONE,$script:V_HB) {
        if ($job -match "#0*$pv\b") { throw "Job must not write protocol var #$pv." }
    }
}

# Write the idle loop and prompt the operator to bootstrap it with one Start.
function Initialize-Dispatcher {
    Connect-Ddcs
    [System.IO.File]::WriteAllText($script:DispPath, (Build-Dispatcher 0 "(idle - no job)"))
    "Wrote idle $script:DispName to $script:Cnc."
    "==> On the panel: select $script:DispName and press Start ONCE to bootstrap the loop."
    "    Then run Get-DdcsStatus and confirm #$($script:V_HB) (heartbeat) is incrementing."
}

# Push a job: bump id, build file, ATOMIC write (temp -> rename), return the id.
function Send-DdcsJob([string]$GCode) {
    Connect-Ddcs
    Test-JobSafe $GCode
    $id = 1
    if (Test-Path $script:IdFile) { $id = [int](Get-Content $script:IdFile) + 1 }
    Set-Content -Path $script:IdFile -Value $id
    [System.IO.File]::WriteAllText($script:TmpPath, (Build-Dispatcher $id $GCode))
    Move-Item -Force -Path $script:TmpPath -Destination $script:DispPath   # atomic-ish rename into place
    "Sent job id=$id (atomic). Poll with: Wait-DdcsJob $id"
    return $id
}

# Poll for completion. DONE = #244 reached id. ERROR = started but stalled (likely syntax error halted loop).
function Wait-DdcsJob([int]$Id, [int]$TimeoutSec = 20) {
    Connect-Ddcs
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if ((Read-DdcsVar $script:V_DONE) -eq $Id) {
            return [pscustomobject]@{ Id=$Id; Status="DONE" }
        }
        Start-Sleep -Milliseconds 300
    }
    if ((Read-DdcsVar $script:V_START) -eq $Id) {
        return [pscustomobject]@{ Id=$Id; Status="ERROR/STALLED — started but never finished (likely a syntax error halted the loop; re-bootstrap with one Start)" }
    }
    return [pscustomobject]@{ Id=$Id; Status="TIMEOUT — job not picked up (loop not running? re-bootstrap)" }
}

function Get-DdcsStatus {
    Connect-Ddcs
    [pscustomobject]@{
        heartbeat = Read-DdcsVar $script:V_HB
        cmd_id    = Read-DdcsVar $script:V_CMD
        last_done = Read-DdcsVar $script:V_LAST
        started   = Read-DdcsVar $script:V_START
        done      = Read-DdcsVar $script:V_DONE
    }
}
