@echo off
rem Runs the automated tests (silent, uses temporary files only).
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run "Run Spotify Replica.bat" once first to set things up.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m pytest tests -v
pause
