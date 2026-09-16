@echo off
title XION VPN - Shortcut Installer
cd /d "%~dp0"

echo ========================================================
echo       CREATING XION VPN DESKTOP ^& START MENU SHORTCUTS
echo ========================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_shortcuts.ps1"

echo.
echo [✓] Done! You can now launch XION VPN from your Desktop or Start Menu.
echo.
pause
