@echo off
REM Start the Keshav Mahavidyalaya RAG helpdesk chatbot on Windows.
REM The server listens on all network interfaces so phones, tablets and
REM other computers on the same Wi-Fi/LAN can use it.

cd /d "%~dp0"

REM Build the vector index the first time (or refresh it) - safe to run repeatedly.
".venv\Scripts\python.exe" ingest.py

echo.
echo Starting the helpdesk server...
echo (Local and network URLs are printed below once it is ready.)
echo.
".venv\Scripts\python.exe" app.py

pause
