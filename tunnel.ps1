#requires -Version 5.1
<#
  Starts the Keshav Buddy helpdesk (if not already running) and opens a public
  Cloudflare quick tunnel so the chatbot is reachable from ANY device/network.

  Usage:  double-click tunnel.bat   (or)   powershell -ExecutionPolicy Bypass -File tunnel.ps1
#>

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$cloudflared = Join-Path $root "tools\cloudflared.exe"
$port = if ($env:HELPDESK_PORT) { $env:HELPDESK_PORT } else { "5000" }

function Test-Port($p) {
    (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) -ne $null
}

if (-not (Test-Path $cloudflared)) {
    Write-Host "cloudflared.exe not found at $cloudflared" -ForegroundColor Red
    Write-Host "Download it with: tools\download-cloudflared.ps1" -ForegroundColor Yellow
    exit 1
}

# 1. Make sure the helpdesk server is running.
if (-not (Test-Port $port)) {
    Write-Host "Starting helpdesk server on port $port ..." -ForegroundColor Cyan
    Start-Process -FilePath $python -ArgumentList "app.py" -WorkingDirectory $root -WindowStyle Minimized
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        if (Test-Port $port) { break }
    }
    if (-not (Test-Port $port)) {
        Write-Host "Server did not start in time. Run run.bat first to check for errors." -ForegroundColor Red
        exit 1
    }
}
Write-Host "Helpdesk server is running on http://localhost:$port" -ForegroundColor Green

# 2. Open the quick tunnel and capture the public URL.
Write-Host "Opening a public Cloudflare tunnel ..." -ForegroundColor Cyan
Write-Host "(This creates a temporary https URL that works from any network.)`n"

$log = Join-Path $env:TEMP "keshav_tunnel.log"
if (Test-Path $log) { Remove-Item $log -Force }

$proc = Start-Process -FilePath $cloudflared `
    -ArgumentList "tunnel", "--url", "http://localhost:$port", "--no-autoupdate", "--logfile", $log `
    -WindowStyle Hidden -PassThru

$publicUrl = $null
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Path $log) {
        $match = Select-String -Path $log -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -ErrorAction SilentlyContinue |
                 Select-Object -First 1
        if ($match) { $publicUrl = $match.Matches[0].Value; break }
    }
}

if (-not $publicUrl) {
    Write-Host "Could not detect the public URL. Recent tunnel log:" -ForegroundColor Yellow
    if (Test-Path $log) { Get-Content $log -Tail 20 }
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    exit 1
}

Write-Host ""
Write-Host "  ==============================================================" -ForegroundColor Yellow
Write-Host "   PUBLIC URL (works on ANY device / network):" -ForegroundColor Yellow
Write-Host "   $publicUrl" -ForegroundColor White -BackgroundColor DarkGreen
Write-Host "  ==============================================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Local (this PC)  : http://localhost:$port"
Write-Host "  Sharing tip      : send the PUBLIC URL to anyone."
Write-Host "  Stop the tunnel  : close this window (Ctrl+C) - the URL stops working."
Write-Host ""

# 3. Keep running and mirror the tunnel log until the user stops it.
try {
    Get-Content -Path $log -Wait | ForEach-Object { if ($_ -match "error|ERR") { Write-Host $_ -ForegroundColor DarkGray } }
}
finally {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
}
