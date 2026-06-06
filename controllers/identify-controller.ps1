# identify-controller.ps1 — fingerprint a connected DDCS to prove V4.1 vs Expert (M350).
#
# WHY: this project targets TWO controllers that behave differently (e.g. Modbus serial is
# Expert-only). Never trust an IP or assumption — confirm the device from its own firmware
# BEFORE acting on it. Run this first.
#
# Usage:   .\identify-controller.ps1 -Ip 10.0.0.50
# Output:  a verdict (V4.1 / EXPERT-M350 / UNKNOWN) plus the evidence it is based on.

param([string]$Ip = "10.0.0.50")

# Establish the guest SMB session the old Samba server needs (harmless if already up).
cmd /c "net use \\$Ip\IPC`$ /user:guest `"`"" 2>$null | Out-Null

$sys = "\\$Ip\sysdisk"
if (-not (Test-Path $sys)) { Write-Host "UNKNOWN - cannot reach $sys (SMB session / IP / share?)"; exit 2 }

$keys = 'DDCSV4','DDCSE','Expert','M350','MSETDATA','MGETDATA','Modbus'
$present = @{}; foreach ($k in $keys) { $present[$k] = $false }

# The firmware binary name itself is the first tell: V4.x ships 'ddcsv4.out'.
$fw = Get-ChildItem $sys -Force -ErrorAction SilentlyContinue |
      Where-Object { $_.Name -like '*.out' } | Select-Object -First 1
$fwName = if ($fw) { $fw.Name } else { '(none found)' }

# Scan the firmware for model + Modbus (Expert-only) strings.
if ($fw) {
    $txt = [System.Text.Encoding]::ASCII.GetString([System.IO.File]::ReadAllBytes($fw.FullName))
    foreach ($k in $keys) { $present[$k] = [bool]($txt -match [regex]::Escape($k)) }  # case-insensitive
}

$isV4     = ($fwName -eq 'ddcsv4.out') -or $present['DDCSV4']
$isExpert = $present['DDCSE'] -or $present['Expert'] -or $present['M350'] -or `
            $present['MSETDATA'] -or $present['MGETDATA'] -or $present['Modbus']

$verdict = if ($isV4 -and -not $isExpert) { "V4.1 (bench)" }
           elseif ($isExpert -and -not $isV4) { "EXPERT-M350 (target)" }
           else { "UNKNOWN - mixed/no signals, inspect manually" }

Write-Host "=== DDCS identity @ $Ip ==="
Write-Host "  firmware binary : $fwName"
Write-Host "  model strings   : DDCSV4=$($present['DDCSV4'])  DDCSE=$($present['DDCSE'])  Expert=$($present['Expert'])  M350=$($present['M350'])"
Write-Host "  modbus (Expert) : MSETDATA=$($present['MSETDATA'])  MGETDATA=$($present['MGETDATA'])  Modbus=$($present['Modbus'])"
Write-Host "  VERDICT         : $verdict"
