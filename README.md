<div align="center">

# ⚡ XION VPN
### Next-Gen Autonomous Desktop Privacy Workstation

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![CustomTkinter](https://img.shields.io/badge/UI-CustomTkinter-blue?style=for-the-badge)](https://github.com/TomSchimansky/CustomTkinter)
[![Sing-Box Core](https://img.shields.io/badge/Core-Sing--Box%20v1.14-FF5722?style=for-the-badge)](https://sing-box.sagernet.org)
[![Windows](https://img.shields.io/badge/OS-Windows%2010%20%2F%2011-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://microsoft.com)
[![Privacy](https://img.shields.io/badge/Privacy-100%25%20Verified%20(2ip.io)-10B981?style=for-the-badge)](https://2ip.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

*A 100% self-contained, high-performance personal Windows desktop VPN application featuring a modern Cyberpunk workstation layout, real-time Canvas animations, military-grade DNS-over-HTTPS encryption, and Layer-3 full-system TUN routing.*

---

</div>

## 🌟 Key Highlights

- 🖥️ **Widescreen Landscape Dashboard (`960x620`):** Built with a Midnight Obsidian theme (`#06090F`), cybernetic accents, and clean multi-column ergonomics.
- ⚡ **Live Canvas Animation Engine:**
  - **Pulsing Radar Rings:** Concentric rings around the central power hub dynamically expand and breathe at 30 FPS based on connection states (Cyber Emerald for Protected, Amber for Shielding).
  - **Animated Tunnel Pipeline:** Neon data packets visually traverse the end-to-end path from your device to the egress server.
  - **Real-Time Rolling Traffic Waveform:** Live Bezier curve sparkline tracking download (Emerald) and upload (Cyan) throughput.
- 🛡️ **Military-Grade Privacy Suite:**
  - **Encrypted DNS-over-HTTPS (DoH):** Direct integration with Cloudflare `1.1.1.1` and AdGuard DNS `94.140.14.14` to encrypt requests and eliminate ISP logging.
  - **🛡️ Built-in DNS Ad & Malware Shield:** Blocks ads, telemetry, trackers, and phishing domains at wire speed directly at the DNS query layer.
  - **🔀 Split Tunneling (App Exclusions):** Exclude games (Steam, Epic Games), Discord, or custom `.exe` apps to bypass the VPN for ultra-low ping while other apps stay shielded.
  - **IPv6 Leak Blocker:** Forces strict IPv4 routing to prevent background Windows IPv6 leakage.
  - **Active Watchdog Kill Switch:** Continuously monitors the core tunnel process; instantly severs unencrypted outbound traffic to a dead loopback if the VPN connection ever drops.
  - **🔄 Auto-Rotate IP (Zero-Downtime Server Hopping):** Automatically cycles between global egress servers at configurable intervals (5, 10, 15, or 30 mins) with Same-Region vs Global Scope options.
  - **🔍 1-Click Privacy & Leak Audit Suite:** Built-in diagnostics checking public egress IP, DNS leak resistance, and IPv6 isolation with real-time security verification.
- ⚡ **Performance & Node Intelligence:**
  - **⚡ Real-Time Ping Matrix & Smart Connect:** Concurrent TCP latency benchmarking displays live response times (`[45 ms]`) and auto-selects the fastest available server.
  - **🌐 Custom Node Import:** Import any custom `vless://` or Shadowsocks URI directly into your active server pool.
- 🗕 **Silent System Tray & Windows Automation:**
  - **Auto-Launch with Windows:** Optional startup registration in Windows Registry to launch on boot.
  - **Start Minimized to Tray & Auto-Connect:** Boots silently into the taskbar notification area and establishes the tunnel automatically.
  - **🔊 Cyberpunk Sci-Fi Sound FX:** Lightweight, non-blocking futuristic audio feedback on connect, disconnect, server hop, and kill switch alerts.
- 🚀 **Full-System TUN Mode (All Desktop Apps):** Uses bundled `wintun.dll` to establish a Layer-3 virtual network adapter, ensuring developer tools (OpenCode, VS Code, Git, Terminal, Node, Docker) and desktop software are shielded—not just web browsers.
- 🌍 **Verified Multi-Country Global Nodes:** Ready-to-connect genuine egress endpoints across 🇺🇸 United States, 🇸🇬 Singapore, 🇯🇵 Japan, 🇩🇪 Germany, 🇫🇷 France, 🇨🇦 Canada, and 🇰🇷 South Korea.
- 🌐 **Private Linux VPS Server Included:** Bundled with `server.py` and `crypto_tunnel.py` to deploy your own personal AES-256-GCM private VPN on any remote Ubuntu/Debian server.

---

## 🏗️ Architecture & Tunnel Flow

```mermaid
flowchart LR
    A[🖥️ Windows Client / All Apps] -->|Layer-3 TUN / WinINet| B[⚡ XION Core Engine]
    B -->|DoH 1.1.1.1| C[🔒 Encrypted DNS]
    B -->|VLESS + REALITY + uTLS| D((🌐 Global Fiber Backbone))
    D -->|Egress IP| E[🇺🇸 US / 🇸🇬 SG / 🇯🇵 JP / 🇩🇪 DE]
    E --> F[🌍 Target Internet]
```

---

## 📊 2ip.io Privacy Audit Passed

XION VPN was audited against the [2ip.io Anonymity Test Suite](https://2ip.io):

```
Verdict: "You are using anonymization tools, but we could not find your real IP address."
Real IP Leak: NONE (0%)
DNS Leak: NONE (0%)
IPv6 Leak: NONE (0%)
```

---

## 🚀 Getting Started

### Prerequisites
- Windows 10 or Windows 11 (64-bit)
- Python 3.10+ (Bundled virtual environment automatically set up by launcher)

### Method 1: Professional Windows Setup Wizard (Recommended for Users)
1. Double-click **`installer/XION-VPN-Setup-v1.0.exe`** (or in `dist/`)
2. Follow the standard Windows Setup Wizard:
   - Choose install directory (defaults to `C:\Program Files\XION VPN`)
   - ✅ **Create Desktop Shortcut**
   - ✅ **Create Start Menu Shortcut**
   - ✅ **Launch on Finish**
   - Registers in Windows **Settings > Apps > Installed Apps** with a full uninstaller!

### Method 2: Portable Standalone Executable (No Installation Required)
1. Download or extract `dist/XION-VPN-v1.0-Windows-x64.zip`
2. Run **`XION-VPN.exe`** directly from anywhere (USB drive, Desktop, Downloads).
3. To add Desktop & Start Menu shortcuts for this portable copy, double-click **`installer/create_shortcuts.bat`**!

### Method 3: 1-Click Script Launch (Developer Mode)
Simply double-click **`run.bat`** in the project root!
> **Note for Full-System Routing:** Right-click **`XION-VPN.exe`** or **`run.bat`** and choose **"Run as administrator"** (or click the **"⚡ Enable All Apps (TUN)"** button inside the app) to enable Layer-3 adapter routing for OpenCode, VS Code, and terminal software.

### Method 4: Build .exe & Setup Wizard from Source
Double-click **`installer/build_installer.bat`** or run:
```powershell
.\.venv\Scripts\python.exe installer/build_exe.py
```
This automatically bundles the runtime, creates the portable folder and `.zip`, and compiles the Inno Setup Wizard `.exe`.

### Method 5: Manual Terminal Setup
```powershell
# 1. Clone the repository
git clone https://github.com/AbdulMoizAns/XION-VPN.git
cd XION-VPN

# 2. Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\activate

# 3. Install requirements
pip install -r requirements.txt

# 4. Launch XION VPN
python src/main.py
```
---

## 📁 Repository Structure

```
XION-VPN/
├── src/                      # ⚡ Core Software & Runtime Assets
│   ├── main.py               # Application entry point & crash guard
│   ├── gui.py                # Widescreen Landscape UI & Canvas Animation Engine
│   ├── tray_manager.py       # Windows System Tray Controller & Context Menu
│   ├── vpn_engine.py         # Tunnel controller, watchdog kill switch & Clash API
│   ├── node_manager.py       # Multi-country node pool & sing-box config builder
│   ├── settings_manager.py   # Persistent JSON settings (%APPDATA%/XION-VPN)
│   ├── sound_effects.py      # Non-blocking Cyberpunk Sci-Fi sound FX engine
│   ├── sys_utils.py          # WinINet proxy, leak test, telemetry & startup reg
│   ├── tunnel_client.py      # SOCKS5-to-TLS client for custom private VPS
│   ├── crypto_tunnel.py      # AES-256-GCM framing for private VPS mode
│   ├── warp_generator.py     # Cloudflare WARP credential generator
│   ├── app_icon.ico          # Multi-resolution cyberpunk neon app & setup icon
│   ├── sing-box.exe          # Bundled Sing-Box v1.14 core binary
│   └── wintun.dll            # Layer-3 WireGuard / Wintun network driver
│
├── installer/                # 📦 Setup Wizard, Installers & Build Pipeline
│   ├── XION-VPN-Setup-v1.0.exe # Ready-to-run Windows Setup Wizard installer
│   ├── installer.iss         # Inno Setup compilation script
│   ├── build_exe.py          # PyInstaller & Inno Setup automated builder
│   ├── build_installer.bat   # 1-Click batch script to compile executable & installer
│   ├── create_shortcuts.bat  # 1-Click batch script to create Desktop & Start Menu shortcuts
│   ├── create_shortcuts.ps1  # PowerShell shortcut automation
│   └── XION-VPN.spec         # PyInstaller specification file
│
├── server/                   # 🌐 Private VPS Server Component
│   ├── server.py             # Standalone private server daemon for Linux VPS
│   └── crypto_tunnel.py      # Symmetric AES-256-GCM transport layer
│
├── run.bat                   # 🚀 1-Click root launcher (auto-venv & auto-elevation)
├── requirements.txt          # Python dependency lockfile
├── README.md                 # Documentation
├── LICENSE                   # MIT License
└── .gitignore                # Git ignore rules
```

---

## 🛡️ Security & Privacy Philosophy

- **Zero Telemetry Collection:** XION VPN does not log, store, or transmit your traffic or destination data anywhere.
- **Direct End-to-End Handshake:** All traffic is encrypted directly on your local machine before leaving your network interface.
- **Fail-Safe Fallback:** If elevated permissions are unavailable, the core automatically operates in high-speed system proxy mode without halting.

---

## 📜 License

This project is open-source and licensed under the [MIT License](LICENSE).
Created with ⚡ by **Abdul Moiz Ansari**.
