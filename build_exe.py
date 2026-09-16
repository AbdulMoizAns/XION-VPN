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

    icon_src = os.path.join(BASE_DIR, "app_icon.ico")
    cmd = [
        pyinstaller_exe,
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name=XION-VPN",
        "--collect-all=customtkinter",
        f"--add-data={wintun_src};.",
        f"--add-data={singbox_src};.",
    ]
    if os.path.isfile(icon_src):
        cmd.append(f"--icon={icon_src}")
        cmd.append(f"--add-data={icon_src};.")

    cmd.append(os.path.join(BASE_DIR, "main.py"))

    print(f"[*] Running PyInstaller...")
    res = subprocess.run(cmd, cwd=BASE_DIR)
    if res.returncode != 0:
        print("[-] Build failed during PyInstaller compilation.")
        sys.exit(res.returncode)

    # 3. Post-build: Ensure sing-box.exe, wintun.dll, app_icon.ico exist directly in output app folder
    print("[*] Verifying binary payloads in output directory...")
    target_singbox = os.path.join(OUTPUT_APP_DIR, "sing-box.exe")
    target_wintun = os.path.join(OUTPUT_APP_DIR, "wintun.dll")

    if not os.path.isfile(target_singbox):
        shutil.copy2(singbox_src, target_singbox)

    if not os.path.isfile(target_wintun):
        shutil.copy2(wintun_src, target_wintun)

    if os.path.isfile(icon_src):
        shutil.copy2(icon_src, os.path.join(OUTPUT_APP_DIR, "app_icon.ico"))

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

    # 6. Inno Setup Compiler (Setup Wizard .exe)
    setup_exe_path = None
    iscc_candidates = [
        shutil.which("iscc"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"),
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
    ]
    iscc_exe = next((p for p in iscc_candidates if p and os.path.isfile(p)), None)
    iss_file = os.path.join(BASE_DIR, "installer.iss")

    if iscc_exe and os.path.isfile(iss_file):
        print(f"[*] Compiling Inno Setup Wizard using {iscc_exe}...")
        iscc_res = subprocess.run([iscc_exe, iss_file], cwd=BASE_DIR)
        if iscc_res.returncode == 0:
            setup_exe_path = os.path.join(DIST_DIR, "XION-VPN-Setup-v1.0.exe")

    print("=" * 60)
    print(" [+] BUILD SUCCESSFUL!")
    print(f" [+] Executable Folder: {OUTPUT_APP_DIR}")
    print(f" [+] Main Binary:       {os.path.join(OUTPUT_APP_DIR, 'XION-VPN.exe')}")
    print(f" [+] Release Package:   {zip_path}")
    if setup_exe_path and os.path.isfile(setup_exe_path):
        print(f" [+] Setup Wizard (.exe): {setup_exe_path}")
    print("=" * 60)

if __name__ == "__main__":
    build()
