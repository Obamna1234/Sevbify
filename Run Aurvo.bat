@echo off
rem ===================================================================
rem  One-click launcher. Double-click this file to start the app.
rem  First run: creates a private Python environment (.venv) and installs
rem  the packages (takes a minute). Later runs start straight away, and
rem  packages are re-installed automatically only when requirements.txt
rem  changes (e.g. after pulling an update in GitHub Desktop).
rem ===================================================================
setlocal
cd /d "%~dp0"
title Aurvo launcher

where py >nul 2>nul
if errorlevel 1 (
    echo.
    echo  Python was not found.
    echo  Install 64-bit Python 3.12 from https://www.python.org/downloads/
    echo  and tick "Add python.exe to PATH" during setup, then run this again.
    echo.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python environment - first run only...
    py -3 -m venv .venv
    if errorlevel 1 goto :failed
)

fc /b requirements.txt ".venv\installed-requirements.txt" >nul 2>nul
if errorlevel 1 (
    echo Installing / updating packages...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet
    if errorlevel 1 goto :failed
    copy /y requirements.txt ".venv\installed-requirements.txt" >nul
)

rem pythonw = no console window behind the app
start "" ".venv\Scripts\pythonw.exe" app.py
exit /b 0

:failed
echo.
echo  Setup failed - see the messages above. Check your internet connection
echo  and run this file again.
echo.
pause
exit /b 1
