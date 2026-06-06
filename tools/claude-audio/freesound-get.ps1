# freesound-get.ps1 - download a freesound HQ-mp3 preview by sound ID using the local API key.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File freesound-get.ps1 -Id 109662 [-OutName success.mp3]
param([Parameter(Mandatory = $true)][string]$Id, [string]$OutName)
$root = Join-Path $env:USERPROFILE ".claude"
$token = (Get-Content (Join-Path $root "freesound-token.txt") -Raw).Trim()
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = 'SilentlyContinue'
$info = Invoke-RestMethod -Uri "https://freesound.org/apiv2/sounds/$Id/?fields=id,name,username,license,previews&token=$token"
$prev = $info.previews.'preview-hq-mp3'
$sounds = Join-Path $root "sounds"; New-Item -ItemType Directory -Force $sounds | Out-Null
if (-not $OutName) { $OutName = "fs_$Id.mp3" }
$out = Join-Path $sounds $OutName
Invoke-WebRequest -UseBasicParsing -Uri $prev -OutFile $out
"id=$($info.id)  name='$($info.name)'  by=$($info.username)  license='$($info.license)'"
"saved -> $out ($([math]::Round((Get-Item $out).Length/1KB)) KB)"
