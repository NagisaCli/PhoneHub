@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM Start background Python server if not already running
powershell -NoProfile -Command "$conn = Test-NetConnection -ComputerName 127.0.0.1 -Port 18080 -InformationLevel Quiet; if (-not $conn) { Start-Process python -ArgumentList 'server.py 18080' -WorkingDirectory '%~dp0' -WindowStyle Hidden; Start-Sleep -Milliseconds 900 }"

REM Launch Microsoft Edge App Mode without proxy
set "EDGE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE%" set "EDGE=C:\Program Files\Microsoft\Edge\Application\msedge.exe"

if exist "%EDGE%" (
    start "" "%EDGE%" --app="http://127.0.0.1:18080/" --no-proxy-server
) else (
    start http://127.0.0.1:18080/
)
