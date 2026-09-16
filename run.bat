@echo off
title XION VPN
cd /d "%~dp0"

echo ========================================================
echo                 STARTING XION VPN...
echo ========================================================

set PYTHON_EXE="%~dp0.venv\Scripts\python.exe"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

REM Check if Python venv exists
if not exist %PYTHON_EXE% (
    echo [*] Setting up virtual environment...
    python -m venv "%~dp0.venv"
    echo [*] Installing dependencies from requirements.txt...
    "%~dp0.venv\Scripts\pip.exe" install -r "%~dp0requirements.txt"
)

REM Check administrator mode
net session >nul 2>&1
if %errorlevel% == 0 (
    echo [OK] Running with Administrator Privileges - Full System TUN Mode enabled.
) else (
    echo [NOTE] Running in Standard Mode. For OpenCode, click Enable All Apps in app.
)

echo [*] Launching XION VPN GUI...
%PYTHON_EXE% "%~dp0main.py"

if %errorlevel% neq 0 (
    echo.
    echo [-] Application stopped with exit code %errorlevel%.
    pause
)
