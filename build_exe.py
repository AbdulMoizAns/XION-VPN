"""
build_exe.py - Automated Standalone Executable Packaging for XION VPN
Uses PyInstaller to bundle Python runtime, CustomTkinter, Wintun driver, and Sing-Box core.
"""
import os
import shutil
import subprocess
import sys
import zipfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, "dist")
BUILD_DIR = os.path.join(BASE_DIR, "build")
OUTPUT_APP_DIR = os.path.join(DIST_DIR, "XION-VPN")

def build():
    print("=" * 60)
    print("       BUILDING XION VPN STANDALONE EXECUTABLE")
    print("=" * 60)

    # 1. Verify required bundled files exist
    singbox_src = os.path.join(BASE_DIR, "sing-box.exe")
    wintun_src = os.path.join(BASE_DIR, "wintun.dll")

    if not os.path.isfile(singbox_src):
        print(f"[-] ERROR: {singbox_src} not found!")
        sys.exit(1)

    if not os.path.isfile(wintun_src):
        print(f"[-] ERROR: {wintun_src} not found!")
        sys.exit(1)

    # 2. PyInstaller Command Arguments
    pyinstaller_exe = os.path.join(BASE_DIR, ".venv", "Scripts", "pyinstaller.exe")
    if not os.path.isfile(pyinstaller_exe):
        pyinstaller_exe = "pyinstaller"

    cmd = [
        pyinstaller_exe,
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name=XION-VPN",
        "--collect-all=customtkinter",
        f"--add-data={wintun_src};.",
        f"--add-data={singbox_src};.",
        os.path.join(BASE_DIR, "main.py")
    ]

    print(f"[*] Running PyInstaller...")
    res = subprocess.run(cmd, cwd=BASE_DIR)
    if res.returncode != 0:
        print("[-] Build failed during PyInstaller compilation.")
        sys.exit(res.returncode)

    # 3. Post-build: Ensure sing-box.exe and wintun.dll exist directly in output app folder
    print("[*] Verifying binary payloads in output directory...")
    target_singbox = os.path.join(OUTPUT_APP_DIR, "sing-box.exe")
    target_wintun = os.path.join(OUTPUT_APP_DIR, "wintun.dll")

    if not os.path.isfile(target_singbox):
        shutil.copy2(singbox_src, target_singbox)

    if not os.path.isfile(target_wintun):
        shutil.copy2(wintun_src, target_wintun)

    # Copy README and LICENSE to output folder
    for fname in ["README.md", "LICENSE"]:
        src = os.path.join(BASE_DIR, fname)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(OUTPUT_APP_DIR, fname))

    # 4. Create 1-Click Launch Launcher inside dist/XION-VPN
    launcher_bat = os.path.join(OUTPUT_APP_DIR, "Launch XION VPN.bat")
    with open(launcher_bat, "w", encoding="utf-8") as f:
        f.write('@echo off\r\nstart "" "%~dp0XION-VPN.exe"\r\n')

    # 5. Create Standalone Portable ZIP archive
    zip_path = os.path.join(DIST_DIR, "XION-VPN-v1.0-Windows-x64.zip")
    print(f"[*] Creating release archive: {zip_path}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(OUTPUT_APP_DIR):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, DIST_DIR)
                zf.write(abs_path, rel_path)

    print("=" * 60)
    print(" [+] BUILD SUCCESSFUL!")
    print(f" [+] Executable Folder: {OUTPUT_APP_DIR}")
    print(f" [+] Main Binary:       {os.path.join(OUTPUT_APP_DIR, 'XION-VPN.exe')}")
    print(f" [+] Release Package:   {zip_path}")
    print("=" * 60)

if __name__ == "__main__":
    build()
