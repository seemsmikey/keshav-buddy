@echo off
REM Open a public Cloudflare tunnel so Keshav Buddy is reachable from any device.
REM Double-click this file. Close the window to stop the tunnel.

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tunnel.ps1"
pause
