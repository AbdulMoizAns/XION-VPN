@echo off
title XION VPN - Executable Builder
cd /d "%~dp0"

echo ========================================================
echo          XION VPN STANDALONE BUILD PIPELINE
echo ========================================================

set PYTHON_EXE="%~dp0.venv\Scripts\python.exe"

if not exist %PYTHON_EXE% (
    echo [-] Python virtual environment not found. Please run run.bat first.
    pause
    exit /b 1
)

echo [*] Checking PyInstaller...
%PYTHON_EXE% -m pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Installing PyInstaller...
    %PYTHON_EXE% -m pip install pyinstaller
)

echo [*] Compiling standalone Windows application...
%PYTHON_EXE% "%~dp0build_exe.py"

if %errorlevel% neq 0 (
    echo.
    echo [-] Build failed with error code %errorlevel%.
    pause
    exit /b %errorlevel%
)

echo.
echo [*] Opening dist folder...
start explorer "%~dp0dist"
pause
