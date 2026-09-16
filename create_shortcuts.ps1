# create_shortcuts.ps1 - Creates Desktop & Start Menu shortcuts for XION VPN
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExePath = Join-Path $ScriptDir "dist\XION-VPN\XION-VPN.exe"
$IconPath = Join-Path $ScriptDir "app_icon.ico"

if (-not (Test-Path $ExePath)) {
    $ExePath = Join-Path $ScriptDir "run.bat"
}

$WshShell = New-Object -ComObject WScript.Shell

# 1. Desktop Shortcut
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$DesktopShortcutPath = Join-Path $DesktopPath "XION VPN.lnk"
$Shortcut = $WshShell.CreateShortcut($DesktopShortcutPath)
$Shortcut.TargetPath = $ExePath
$Shortcut.WorkingDirectory = Split-Path -Parent $ExePath
$Shortcut.Description = "XION VPN - Next-Gen Autonomous Privacy Workstation"
if (Test-Path $IconPath) {
    $Shortcut.IconLocation = "$IconPath, 0"
}
$Shortcut.Save()
Write-Host "[+] Desktop shortcut created at: $DesktopShortcutPath" -ForegroundColor Green

# 2. Start Menu Shortcut
$StartMenuPath = [Environment]::GetFolderPath("Programs")
$AppGroupDir = Join-Path $StartMenuPath "XION VPN"
if (-not (Test-Path $AppGroupDir)) {
    New-Item -ItemType Directory -Path $AppGroupDir -Force | Out-Null
}
$StartMenuShortcutPath = Join-Path $AppGroupDir "XION VPN.lnk"
$StartShortcut = $WshShell.CreateShortcut($StartMenuShortcutPath)
$StartShortcut.TargetPath = $ExePath
$StartShortcut.WorkingDirectory = Split-Path -Parent $ExePath
$StartShortcut.Description = "XION VPN - Next-Gen Autonomous Privacy Workstation"
if (Test-Path $IconPath) {
    $StartShortcut.IconLocation = "$IconPath, 0"
}
$StartShortcut.Save()
Write-Host "[+] Start Menu shortcut created at: $StartMenuShortcutPath" -ForegroundColor Green
