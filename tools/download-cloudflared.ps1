#requires -Version 5.1
# Downloads the cloudflared binary used by tunnel.ps1 / tunnel.bat.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$toolsDir = Join-Path $root "tools"
$target = Join-Path $toolsDir "cloudflared.exe"

New-Item -ItemType Directory -Path $toolsDir -Force | Out-Null

$url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
Write-Host "Downloading cloudflared from $url ..." -ForegroundColor Cyan
Invoke-WebRequest -Uri $url -OutFile $target -UseBasicParsing -TimeoutSec 300

Write-Host "Saved to $target" -ForegroundColor Green
& $target --version
