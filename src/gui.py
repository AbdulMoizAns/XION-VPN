"""
gui.py - Beast-Mode Widescreen Landscape Dashboard for XION VPN
Built with CustomTkinter for Windows.
Features:
- Widescreen 960x620 Cyberpunk Workstation Layout
- Canvas-based Animated Pulsing Power Hub & Radar Rings
- Live Rolling Traffic Waveforms (Download & Upload Sparklines)
- Interactive End-to-End Tunnel Route Visualizer
- Real-time Multi-Metric Telemetry (Ping, Speeds, Session Volume, Monthly Volume)
- Military-Grade Security Controls (DoH 1.1.1.1 / AdGuard, IPv6 Shield, Kill Switch)
- Split Tunneling (Application & Process Exclusions)
- Built-in 1-Click Privacy & Leak Audit Tool
- Settings Automation (Launch with Windows, Start Minimized, Auto-Connect, Sound FX)
- Custom VLESS Node Import & Private Linux VPS Mode
"""
import math
import os
import re
import sys
import threading
import time
from collections import deque
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox

from sys_utils import (
    get_public_ip_info,
    measure_latency,
    NetworkStatsTracker,
    is_admin,
    restart_as_admin,
    set_windows_system_proxy,
    set_windows_startup,
    get_windows_startup_status,
    run_leak_test
)
from vpn_engine import (
    VpnEngine,
    STATE_DISCONNECTED,
    STATE_CONNECTING,
    STATE_CONNECTED,
    STATE_ERROR
)
from node_manager import (
    fetch_live_nodes,
    BUILTIN_FAST_NODES,
    update_all_node_pings,
    get_cached_ping,
    import_custom_vless
)
from settings_manager import settings_mgr
from sound_effects import play_connect, play_disconnect, play_rotate, play_alert
from tray_manager import TrayManager

# Cyberpunk / Midnight Obsidian Palette
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

COLOR_BG = "#06090F"              # Deep midnight obsidian background
COLOR_SIDEBAR = "#090D16"         # Sidebar column background
COLOR_SURFACE = "#0C121E"         # Card background
COLOR_SURFACE_ALT = "#111A2E"     # Elevated card surface
COLOR_BORDER = "#1E2A44"          # Subtle cyberpunk border
COLOR_BORDER_LIGHT = "#2D3E66"    # Active border

COLOR_CYAN = "#00F0FF"            # Cyber Cyan
COLOR_CYAN_DIM = "#0891B2"
COLOR_EMERALD = "#10B981"         # Protected Emerald
COLOR_EMERALD_GLOW = "#059669"
COLOR_EMERALD_BG = "#064E3B"
COLOR_AMBER = "#F59E0B"           # Connecting / Shielding Amber
COLOR_AMBER_BG = "#451A03"
COLOR_RED = "#EF4444"             # Error / Disconnected Red
COLOR_PURPLE = "#8B5CF6"          # Advanced Feature Purple

COLOR_TEXT = "#F8FAFC"
COLOR_TEXT_MUTED = "#94A3B8"
COLOR_TEXT_DIM = "#64748B"


class XionVpnApp(ctk.CTk):
    def __init__(self, start_minimized: bool = False):
        super().__init__()

        self.title("XION VPN - Next-Gen Autonomous Privacy Workstation")
        self.geometry("960x620")
        self.minsize(960, 620)
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG)

        # Set application window and taskbar icon
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_icon.ico")
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            bundle_icon = os.path.join(sys._MEIPASS, "app_icon.ico")
            if os.path.isfile(bundle_icon):
                icon_path = bundle_icon
        if os.path.isfile(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        self.engine = VpnEngine()
        self.engine.on_state_change = self._on_engine_state_change
        self.engine.on_ip_rotated = self._on_ip_rotated
        self.stats_tracker = NetworkStatsTracker()

        # State data
        self.available_nodes = fetch_live_nodes()
        self.current_ip_info = {"ip": "Fetching...", "country": "...", "city": "...", "isp": "..."}
        self.initial_real_ip = "Fetching..."
        self.initial_real_country = "Local ISP"
        self._is_running = True

        # Persistent Settings Variables
        self.kill_switch_var = ctk.BooleanVar(value=settings_mgr.get("kill_switch_enabled", False))
        self.minimize_to_tray_var = ctk.BooleanVar(value=settings_mgr.get("start_minimized", True))
        self.auto_rotate_var = ctk.BooleanVar(value=settings_mgr.get("auto_rotate_enabled", False))
        self.startup_var = ctk.BooleanVar(value=get_windows_startup_status())
        self.sound_fx_var = ctk.BooleanVar(value=settings_mgr.get("sound_effects", True))
        self.ad_block_var = ctk.BooleanVar(value=settings_mgr.get("ad_blocker", True))
        self.malware_var = ctk.BooleanVar(value=settings_mgr.get("malware_shield", True))
        self.split_enabled_var = ctk.BooleanVar(value=settings_mgr.get("split_tunneling_enabled", False))
        self.auto_connect_var = ctk.BooleanVar(value=settings_mgr.get("auto_connect_on_launch", False))

        # Animation & Telemetry states
        self._pulse_phase = 0.0
        self._route_dot_pos = 0.0
        self.down_history = deque([0.0] * 30, maxlen=30)
        self.up_history = deque([0.0] * 30, maxlen=30)
        self.total_bytes_transferred = 0

        self._build_ui()
        self._start_animation_loop()
        self._start_background_loops()

        # Initialize System Tray Manager (runs in background thread)
        self.tray_manager = TrayManager(self)
        self.tray_manager.start()

        # Initial background load
        threading.Thread(target=self._initial_load, daemon=True).start()

        # Handle Start Minimized (e.g. from Windows boot)
        if start_minimized or settings_mgr.get("start_minimized_boot", False):
            self.safe_after(60, self.hide_to_tray)

        # Handle Auto-Connect on Launch
        if self.auto_connect_var.get():
            self.safe_after(1200, self._toggle_connection)

    def safe_after(self, ms: int, func):
        """Thread-safe and destroyed-safe wrapper for Tkinter after()."""
        if getattr(self, "_is_running", True):
            try:
                self.after(ms, func)
            except Exception:
                pass

    def _initial_load(self):
        data = get_public_ip_info()
        self.current_ip_info = data
        self.initial_real_ip = data.get("ip", "Unknown")
        self.initial_real_country = f"{data.get('city', '')}, {data.get('country', '')}".strip(", ") or "Local ISP"
        self.safe_after(0, lambda: self._update_ip_labels(data))
        self._refresh_nodes_dropdown()
        # Measure initial pings in background
        threading.Thread(target=self._ping_check_routine, daemon=True).start()

    def _ping_check_routine(self):
        update_all_node_pings()
        self.safe_after(0, self._refresh_nodes_dropdown)

    def _refresh_nodes_dropdown(self):
        try:
            self.available_nodes = fetch_live_nodes()
            names = []
            for n in self.available_nodes:
                p = get_cached_ping(n.get("tag"))
                if n.get("country_code") == "AUTO":
                    names.append(n["name"])
                elif p and p < 900:
                    names.append(f"{n['name']} [{p} ms]")
                else:
                    names.append(n["name"])

            cur = self.server_dropdown.get()
            clean_cur = re.sub(r"\s*\[\d+\s*ms\]", "", cur).strip()
            self.server_dropdown.configure(values=names)

            # Keep selection if still valid
            for nm in names:
                if clean_cur in nm:
                    self.server_dropdown.set(nm)
                    break
        except Exception:
            pass

    def _build_ui(self):
        # Master Grid Layout (2 Columns: Left Sidebar [345px], Right Main Stage [615px])
        self.grid_columnconfigure(0, weight=0, minsize=345)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # =============================================================
        # LEFT SIDEBAR: Controls, Server Selector & Multi-Tab Feature Suite
        # =============================================================
        sidebar = ctk.CTkFrame(self, fg_color=COLOR_SIDEBAR, corner_radius=0, border_width=1, border_color=COLOR_BORDER)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        # 1. Header & Brand Box
        brand_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand_frame.pack(fill="x", padx=16, pady=(16, 8))

        brand_row = ctk.CTkFrame(brand_frame, fg_color="transparent")
        brand_row.pack(fill="x")

        ctk.CTkLabel(
            brand_row,
            text="⚡ XION",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color="#FFFFFF"
        ).pack(side="left")

        ctk.CTkLabel(
            brand_row,
            text="VPN",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=COLOR_CYAN
        ).pack(side="left", padx=(4, 8))

        tray_btn = ctk.CTkButton(
            brand_row,
            text="🗕 Tray",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=COLOR_SURFACE_ALT,
            hover_color="#1E2A44",
            text_color=COLOR_TEXT_MUTED,
            border_width=1,
            border_color=COLOR_BORDER,
            width=58,
            height=24,
            corner_radius=6,
            command=self.hide_to_tray
        )
        tray_btn.pack(side="right")

        # Mode Badge
        admin = is_admin()
        if admin:
            mode_badge = ctk.CTkLabel(
                brand_frame,
                text="🛡️ FULL-SYSTEM TUN (Layer-3)",
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                text_color="#34D399",
                fg_color=COLOR_EMERALD_BG,
                corner_radius=6,
                padx=8,
                pady=2
            )
            mode_badge.pack(anchor="w", pady=(3, 0))
        else:
            elevate_btn = ctk.CTkButton(
                brand_frame,
                text="⚡ Enable All Apps (TUN)",
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                fg_color="#78350F",
                hover_color="#92400E",
                text_color="#FDE68A",
                corner_radius=6,
                height=24,
                command=restart_as_admin
            )
            elevate_btn.pack(anchor="w", pady=(3, 0))

        # 2. Server Selection Card
        srv_card = ctk.CTkFrame(sidebar, fg_color=COLOR_SURFACE, corner_radius=12, border_width=1, border_color=COLOR_BORDER)
        srv_card.pack(fill="x", padx=14, pady=(6, 8))

        srv_title_row = ctk.CTkFrame(srv_card, fg_color="transparent")
        srv_title_row.pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkLabel(
            srv_title_row,
            text="EGRESS GATEWAY",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=COLOR_TEXT_DIM
        ).pack(side="left")

        refresh_ping_btn = ctk.CTkButton(
            srv_title_row,
            text="⚡ Test Pings",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=COLOR_CYAN,
            fg_color="#0F1F38",
            hover_color="#1E2A44",
            corner_radius=4,
            width=68,
            height=20,
            command=lambda: threading.Thread(target=self._ping_check_routine, daemon=True).start()
        )
        refresh_ping_btn.pack(side="right")

        self.server_dropdown = ctk.CTkOptionMenu(
            srv_card,
            values=[n["name"] for n in self.available_nodes],
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=COLOR_SURFACE_ALT,
            button_color="#1E293B",
            button_hover_color="#334155",
            text_color="#FFFFFF",
            dropdown_fg_color=COLOR_SURFACE_ALT,
            dropdown_text_color="#FFFFFF",
            dropdown_hover_color="#1E293B",
            height=34,
            corner_radius=8,
            command=self._on_server_select
        )
        self.server_dropdown.set(self.available_nodes[0]["name"])
        self.server_dropdown.pack(fill="x", padx=12, pady=(0, 10))

        # 3. Sidebar Tabview (Shield, Split, Audit, Config, Custom)
        side_tabs = ctk.CTkTabview(sidebar, fg_color=COLOR_SURFACE, corner_radius=12, border_width=1, border_color=COLOR_BORDER)
        side_tabs.pack(fill="both", expand=True, padx=14, pady=(0, 12))

        tab_sec = side_tabs.add("🛡️ Shield")
        tab_split = side_tabs.add("🔀 Split")
        tab_audit = side_tabs.add("🔍 Audit")
        tab_config = side_tabs.add("⚙️ Config")
        tab_custom = side_tabs.add("🌐 Custom")

        # -------------------------------------------------------------
        # TAB 1: 🛡️ Shield (Security & Auto-Rotation)
        # -------------------------------------------------------------
        sec_box = ctk.CTkFrame(tab_sec, fg_color="transparent")
        sec_box.pack(fill="both", expand=True, padx=2, pady=2)

        self.ks_switch = ctk.CTkSwitch(
            sec_box,
            text="Active Kill Switch",
            font=ctk.CTkFont(size=11, weight="bold"),
            variable=self.kill_switch_var,
            onvalue=True,
            offvalue=False,
            command=self._on_kill_switch_toggle,
            progress_color=COLOR_EMERALD
        )
        self.ks_switch.pack(anchor="w", pady=(2, 1))

        ctk.CTkLabel(
            sec_box,
            text="Blocks all unencrypted traffic if VPN drops unexpectedly.",
            font=ctk.CTkFont(size=9),
            text_color=COLOR_TEXT_DIM,
            wraplength=270,
            justify="left"
        ).pack(anchor="w", padx=(26, 0), pady=(0, 4))

        self.tray_switch = ctk.CTkSwitch(
            sec_box,
            text="Minimize to Tray on Close",
            font=ctk.CTkFont(size=11, weight="bold"),
            variable=self.minimize_to_tray_var,
            onvalue=True,
            offvalue=False,
            command=self._on_minimized_toggle,
            progress_color=COLOR_CYAN
        )
        self.tray_switch.pack(anchor="w", pady=(2, 1))

        # Auto-Rotate IP (Dynamic Server Hopping)
        self.rotate_switch = ctk.CTkSwitch(
            sec_box,
            text="Auto-Rotate IP (Server Hop)",
            font=ctk.CTkFont(size=11, weight="bold"),
            variable=self.auto_rotate_var,
            onvalue=True,
            offvalue=False,
            command=self._on_auto_rotate_toggle,
            progress_color=COLOR_PURPLE
        )
        self.rotate_switch.pack(anchor="w", pady=(2, 1))

        rotate_row = ctk.CTkFrame(sec_box, fg_color="transparent")
        rotate_row.pack(fill="x", padx=(26, 0), pady=(0, 2))

        ctk.CTkLabel(rotate_row, text="Every:", font=ctk.CTkFont(size=9, weight="bold"), text_color=COLOR_TEXT_MUTED).pack(side="left")
        self.rotate_interval_menu = ctk.CTkOptionMenu(
            rotate_row,
            values=["5 Min", "10 Min", "15 Min", "30 Min"],
            font=ctk.CTkFont(size=9, weight="bold"),
            width=68,
            height=20,
            fg_color=COLOR_SURFACE_ALT,
            button_color="#1E293B",
            button_hover_color="#334155",
            text_color=COLOR_CYAN,
            dropdown_fg_color=COLOR_SURFACE_ALT,
            command=self._on_rotation_interval_change
        )
        self.rotate_interval_menu.set("5 Min")
        self.rotate_interval_menu.pack(side="left", padx=(4, 6))

        self.rotate_scope_menu = ctk.CTkOptionMenu(
            rotate_row,
            values=["📍 Same Region", "🌍 Global Hop"],
            font=ctk.CTkFont(size=9, weight="bold"),
            width=110,
            height=20,
            fg_color=COLOR_SURFACE_ALT,
            button_color="#1E293B",
            button_hover_color="#334155",
            text_color=COLOR_EMERALD,
            dropdown_fg_color=COLOR_SURFACE_ALT,
            command=self._on_rotation_scope_change
        )
        self.rotate_scope_menu.set("📍 Same Region")
        self.rotate_scope_menu.pack(side="left")

        sec_badges = ctk.CTkFrame(sec_box, fg_color=COLOR_SURFACE_ALT, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        sec_badges.pack(fill="x", pady=6)

        ctk.CTkLabel(
            sec_badges,
            text="🔒 DoH DNS: Cloudflare & AdGuard (Encrypted)",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=COLOR_CYAN
        ).pack(anchor="w", padx=8, pady=(4, 1))

        ctk.CTkLabel(
            sec_badges,
            text="🛡️ IPv6 Leak Blocker: Active (IPv4 Only)",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=COLOR_EMERALD
        ).pack(anchor="w", padx=8, pady=(1, 4))

        # -------------------------------------------------------------
        # TAB 2: 🔀 Split (Split Tunneling & App Exclusions)
        # -------------------------------------------------------------
        split_box = ctk.CTkFrame(tab_split, fg_color="transparent")
        split_box.pack(fill="both", expand=True, padx=2, pady=2)

        self.split_switch = ctk.CTkSwitch(
            split_box,
            text="Enable Split Tunneling",
            font=ctk.CTkFont(size=11, weight="bold"),
            variable=self.split_enabled_var,
            onvalue=True,
            offvalue=False,
            command=self._on_split_tunnel_toggle,
            progress_color=COLOR_CYAN
        )
        self.split_switch.pack(anchor="w", pady=(2, 1))

        ctk.CTkLabel(
            split_box,
            text="Checked apps bypass VPN tunnel to use direct local internet (lowest ping).",
            font=ctk.CTkFont(size=9),
            text_color=COLOR_TEXT_DIM,
            wraplength=270,
            justify="left"
        ).pack(anchor="w", padx=(26, 0), pady=(0, 4))

        # App Exclusion Presets
        apps_frame = ctk.CTkScrollableFrame(split_box, height=120, fg_color=COLOR_SURFACE_ALT, corner_radius=8)
        apps_frame.pack(fill="both", expand=True, pady=(2, 4))

        preset_apps = [
            ("🎮 Steam", "steam.exe"),
            ("🎮 Epic Games", "epicgameslauncher.exe"),
            ("💬 Discord", "discord.exe"),
            ("🌐 Google Chrome", "chrome.exe"),
            ("📥 qBittorrent", "qbittorrent.exe"),
        ]

        active_apps = [a.lower() for a in settings_mgr.get("split_tunnel_apps", [])]
        self.app_vars = {}

        for label, exe_name in preset_apps:
            var = ctk.BooleanVar(value=exe_name.lower() in active_apps)
            self.app_vars[exe_name] = var
            cb = ctk.CTkCheckBox(
                apps_frame,
                text=label,
                font=ctk.CTkFont(size=10, weight="bold"),
                variable=var,
                command=lambda e=exe_name, v=var: self._on_split_app_toggle(e, v)
            )
            cb.pack(anchor="w", padx=6, pady=2)

        # Custom App Adder
        add_row = ctk.CTkFrame(split_box, fg_color="transparent")
        add_row.pack(fill="x", pady=(2, 0))

        self.custom_app_entry = ctk.CTkEntry(add_row, placeholder_text="process.exe", height=24, font=ctk.CTkFont(size=9), fg_color=COLOR_SURFACE_ALT)
        self.custom_app_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))

        add_app_btn = ctk.CTkButton(
            add_row,
            text="+ Exclude",
            font=ctk.CTkFont(size=9, weight="bold"),
            width=64,
            height=24,
            fg_color="#1E2A44",
            hover_color=COLOR_BORDER_LIGHT,
            command=self._add_custom_split_app
        )
        add_app_btn.pack(side="right")

        # -------------------------------------------------------------
        # TAB 3: 🔍 Audit (1-Click Privacy & Leak Diagnostic Suite)
        # -------------------------------------------------------------
        audit_box = ctk.CTkFrame(tab_audit, fg_color="transparent")
        audit_box.pack(fill="both", expand=True, padx=2, pady=2)

        ctk.CTkLabel(
            audit_box,
            text="1-Click Security & Leak Audit Suite",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#FFFFFF"
        ).pack(anchor="w", pady=(2, 1))

        self.audit_btn = ctk.CTkButton(
            audit_box,
            text="🔍 Run Full Leak Audit",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color="#047857",
            hover_color="#065F46",
            text_color="#FFFFFF",
            height=26,
            command=self._run_leak_audit
        )
        self.audit_btn.pack(fill="x", pady=(4, 6))

        self.audit_results_frame = ctk.CTkFrame(audit_box, fg_color=COLOR_SURFACE_ALT, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        self.audit_results_frame.pack(fill="both", expand=True, pady=(0, 2))

        self.audit_ip_lbl = ctk.CTkLabel(self.audit_results_frame, text="Public IP: Click Run", font=ctk.CTkFont(size=9), text_color=COLOR_TEXT_MUTED)
        self.audit_ip_lbl.pack(anchor="w", padx=8, pady=(4, 1))

        self.audit_loc_lbl = ctk.CTkLabel(self.audit_results_frame, text="Location: --", font=ctk.CTkFont(size=9), text_color=COLOR_TEXT_MUTED)
        self.audit_loc_lbl.pack(anchor="w", padx=8, pady=(1, 1))

        self.audit_dns_lbl = ctk.CTkLabel(self.audit_results_frame, text="DNS Resolver: Cloudflare DoH", font=ctk.CTkFont(size=9), text_color=COLOR_CYAN)
        self.audit_dns_lbl.pack(anchor="w", padx=8, pady=(1, 1))

        self.audit_ipv6_lbl = ctk.CTkLabel(self.audit_results_frame, text="IPv6 Leak: 0% (Shielded)", font=ctk.CTkFont(size=9), text_color=COLOR_EMERALD)
        self.audit_ipv6_lbl.pack(anchor="w", padx=8, pady=(1, 1))

        self.audit_score_lbl = ctk.CTkLabel(
            self.audit_results_frame,
            text="STATUS: 🔒 100% SECURE",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#34D399"
        )
        self.audit_score_lbl.pack(anchor="w", padx=8, pady=(4, 4))

        # -------------------------------------------------------------
        # TAB 4: ⚙️ Config (Automation & Settings)
        # -------------------------------------------------------------
        config_box = ctk.CTkFrame(tab_config, fg_color="transparent")
        config_box.pack(fill="both", expand=True, padx=2, pady=2)

        self.startup_switch = ctk.CTkSwitch(
            config_box,
            text="Launch with Windows",
            font=ctk.CTkFont(size=10, weight="bold"),
            variable=self.startup_var,
            onvalue=True,
            offvalue=False,
            command=self._on_startup_toggle,
            progress_color=COLOR_CYAN
        )
        self.startup_switch.pack(anchor="w", pady=(1, 2))

        self.auto_conn_switch = ctk.CTkSwitch(
            config_box,
            text="Auto-Connect on Launch",
            font=ctk.CTkFont(size=10, weight="bold"),
            variable=self.auto_connect_var,
            onvalue=True,
            offvalue=False,
            command=self._on_auto_connect_toggle,
            progress_color=COLOR_EMERALD
        )
        self.auto_conn_switch.pack(anchor="w", pady=(1, 2))

        self.sound_switch = ctk.CTkSwitch(
            config_box,
            text="Cyberpunk Sound FX",
            font=ctk.CTkFont(size=10, weight="bold"),
            variable=self.sound_fx_var,
            onvalue=True,
            offvalue=False,
            command=self._on_sound_fx_toggle,
            progress_color=COLOR_PURPLE
        )
        self.sound_switch.pack(anchor="w", pady=(1, 2))

        self.ad_switch = ctk.CTkSwitch(
            config_box,
            text="🛡️ Ad & Tracker Shield (DNS)",
            font=ctk.CTkFont(size=10, weight="bold"),
            variable=self.ad_block_var,
            onvalue=True,
            offvalue=False,
            command=self._on_ad_block_toggle,
            progress_color=COLOR_EMERALD
        )
        self.ad_switch.pack(anchor="w", pady=(1, 2))

        self.malware_switch = ctk.CTkSwitch(
            config_box,
            text="☣️ Malware & Phishing Blocker",
            font=ctk.CTkFont(size=10, weight="bold"),
            variable=self.malware_var,
            onvalue=True,
            offvalue=False,
            command=self._on_malware_toggle,
            progress_color=COLOR_AMBER
        )
        self.malware_switch.pack(anchor="w", pady=(1, 2))

        # Historical Data Usage
        data_stats_frame = ctk.CTkFrame(config_box, fg_color=COLOR_SURFACE_ALT, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        data_stats_frame.pack(fill="x", pady=(4, 0))

        tot_gb = settings_mgr.get("total_data_bytes", 0) / (1024 * 1024 * 1024)
        mo_gb = settings_mgr.get("monthly_data_bytes", 0) / (1024 * 1024 * 1024)

        self.history_data_lbl = ctk.CTkLabel(
            data_stats_frame,
            text=f"Total: {tot_gb:.2f} GB | This Month: {mo_gb:.2f} GB",
            font=ctk.CTkFont(family="Consolas", size=9, weight="bold"),
            text_color=COLOR_CYAN
        )
        self.history_data_lbl.pack(padx=8, pady=4)

        # -------------------------------------------------------------
        # TAB 5: 🌐 Custom (Import VLESS & Private VPS)
        # -------------------------------------------------------------
        custom_box = ctk.CTkFrame(tab_custom, fg_color="transparent")
        custom_box.pack(fill="both", expand=True, padx=2, pady=2)

        ctk.CTkLabel(custom_box, text="Import Custom VLESS / Node Link:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#FFFFFF").pack(anchor="w", pady=(2, 2))
        self.custom_uri_entry = ctk.CTkEntry(custom_box, placeholder_text="vless://uuid@host:port?...", height=26, font=ctk.CTkFont(size=9), fg_color=COLOR_SURFACE_ALT)
        self.custom_uri_entry.pack(fill="x", pady=(0, 2))

        import_btn = ctk.CTkButton(
            custom_box,
            text="⚡ Add to Servers",
            font=ctk.CTkFont(size=9, weight="bold"),
            height=22,
            fg_color="#1E2A44",
            hover_color=COLOR_BORDER_LIGHT,
            command=self._import_custom_node
        )
        import_btn.pack(anchor="e", pady=(0, 6))

        # VPS Divider
        ctk.CTkLabel(custom_box, text="Private Linux VPS Mode (server.py):", font=ctk.CTkFont(size=10, weight="bold"), text_color=COLOR_TEXT_DIM).pack(anchor="w", pady=(2, 2))
        self.vps_host = ctk.CTkEntry(custom_box, placeholder_text="VPS IP Address", height=24, font=ctk.CTkFont(size=9), fg_color=COLOR_SURFACE_ALT)
        self.vps_host.insert(0, "127.0.0.1")
        self.vps_host.pack(fill="x", pady=1)

        vps_row = ctk.CTkFrame(custom_box, fg_color="transparent")
        vps_row.pack(fill="x", pady=1)
        self.vps_port = ctk.CTkEntry(vps_row, placeholder_text="8080", width=55, height=24, font=ctk.CTkFont(size=9), fg_color=COLOR_SURFACE_ALT)
        self.vps_port.insert(0, "8080")
        self.vps_port.pack(side="left", padx=(0, 4))
        self.vps_pass = ctk.CTkEntry(vps_row, placeholder_text="Password", show="*", height=24, font=ctk.CTkFont(size=9), fg_color=COLOR_SURFACE_ALT)
        self.vps_pass.insert(0, "xion_secret_pass_2026")
        self.vps_pass.pack(side="left", fill="x", expand=True)

        self.side_tabs = side_tabs

        # =============================================================
        # RIGHT MAIN STAGE: Route Visualizer, Animated Power Hub & Telemetry
        # =============================================================
        main_stage = ctk.CTkFrame(self, fg_color=COLOR_BG)
        main_stage.grid(row=0, column=1, sticky="nsew", padx=18, pady=14)
        main_stage.grid_rowconfigure(1, weight=1)
        main_stage.grid_columnconfigure(0, weight=1)

        # 1. TOP: End-to-End Tunnel Route Visualizer Card
        route_card = ctk.CTkFrame(main_stage, fg_color=COLOR_SURFACE, corner_radius=14, border_width=1, border_color=COLOR_BORDER)
        route_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        route_inner = ctk.CTkFrame(route_card, fg_color="transparent")
        route_inner.pack(fill="x", padx=16, pady=10)

        # Source Box (Your PC)
        src_box = ctk.CTkFrame(route_inner, fg_color="transparent")
        src_box.pack(side="left")
        ctk.CTkLabel(src_box, text="YOUR DEVICE", font=ctk.CTkFont(size=9, weight="bold"), text_color=COLOR_TEXT_DIM).pack(anchor="w")
        self.route_src_ip = ctk.CTkLabel(src_box, text="Fetching...", font=ctk.CTkFont(family="Consolas", size=13, weight="bold"), text_color=COLOR_TEXT)
        self.route_src_ip.pack(anchor="w")
        self.route_src_loc = ctk.CTkLabel(src_box, text="Local Network", font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_MUTED)
        self.route_src_loc.pack(anchor="w")

        # Destination Box (Protected Egress)
        dst_box = ctk.CTkFrame(route_inner, fg_color="transparent")
        dst_box.pack(side="right")
        ctk.CTkLabel(dst_box, text="PROTECTED SHIELD", font=ctk.CTkFont(size=9, weight="bold"), text_color=COLOR_TEXT_DIM).pack(anchor="e")
        self.route_dst_ip = ctk.CTkLabel(dst_box, text="Protected", font=ctk.CTkFont(family="Consolas", size=13, weight="bold"), text_color=COLOR_CYAN)
        self.route_dst_ip.pack(anchor="e")
        self.route_dst_loc = ctk.CTkLabel(dst_box, text="Encrypted Tunnel", font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_MUTED)
        self.route_dst_loc.pack(anchor="e")

        # Center Route Pipe with Animated Neon Dot
        pipe_box = ctk.CTkFrame(route_inner, fg_color="transparent")
        pipe_box.pack(side="left", fill="both", expand=True, padx=20)

        self.route_canvas = tk.Canvas(pipe_box, height=28, bg=COLOR_SURFACE, highlightthickness=0)
        self.route_canvas.pack(fill="x", expand=True, pady=6)

        # 2. CENTER: Animated Radar Power Hub Card
        hero_card = ctk.CTkFrame(main_stage, fg_color=COLOR_SURFACE, corner_radius=16, border_width=1, border_color=COLOR_BORDER)
        hero_card.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        hero_card.grid_columnconfigure(0, weight=1)
        hero_card.grid_rowconfigure(0, weight=1)

        hub_container = ctk.CTkFrame(hero_card, fg_color="transparent")
        hub_container.place(relx=0.5, rely=0.5, anchor="center")

        # Canvas for animated radar pulsing circles
        self.radar_canvas = tk.Canvas(hub_container, width=210, height=210, bg=COLOR_SURFACE, highlightthickness=0)
        self.radar_canvas.pack()

        # Centered Circular Power Button inside Canvas
        self.power_btn = ctk.CTkButton(
            hub_container,
            text="⏻",
            font=ctk.CTkFont(size=44),
            fg_color="#1E293B",
            hover_color="#334155",
            text_color="#38BDF8",
            width=116,
            height=116,
            corner_radius=58,
            command=self._toggle_connection
        )
        self.power_btn.place(relx=0.5, rely=0.45, anchor="center")

        # Dynamic Status Title
        self.status_title = ctk.CTkLabel(
            hub_container,
            text="DISCONNECTED",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=COLOR_TEXT_MUTED
        )
        self.status_title.pack(pady=(2, 1))

        # Dynamic Status Subtitle
        self.status_subtitle = ctk.CTkLabel(
            hub_container,
            text="Tap power hub to activate encrypted shield",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_TEXT_DIM
        )
        self.status_subtitle.pack(pady=(0, 3))

        # Session Timer & Dynamic IP Rotation Pills
        pill_row = ctk.CTkFrame(hub_container, fg_color="transparent")
        pill_row.pack(pady=(1, 0))

        timer_pill = ctk.CTkFrame(pill_row, fg_color=COLOR_SURFACE_ALT, corner_radius=10, border_width=1, border_color=COLOR_BORDER)
        timer_pill.pack(side="left", padx=4)

        self.duration_label = ctk.CTkLabel(
            timer_pill,
            text="⏱️ 00:00:00",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            text_color=COLOR_CYAN,
            padx=10,
            pady=2
        )
        self.duration_label.pack()

        self.rotation_pill = ctk.CTkFrame(pill_row, fg_color=COLOR_SURFACE_ALT, corner_radius=10, border_width=1, border_color=COLOR_BORDER)
        self.rotation_pill.pack(side="left", padx=4)

        self.rotation_label = ctk.CTkLabel(
            self.rotation_pill,
            text="🔄 IP: OFF",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            text_color=COLOR_TEXT_DIM,
            padx=10,
            pady=2
        )
        self.rotation_label.pack()

        # 3. BOTTOM: Telemetry Strip & Real-Time Rolling Waveform Card
        bottom_card = ctk.CTkFrame(main_stage, fg_color=COLOR_SURFACE, corner_radius=14, border_width=1, border_color=COLOR_BORDER)
        bottom_card.grid(row=2, column=0, sticky="ew", pady=(0, 0))

        bottom_grid = ctk.CTkFrame(bottom_card, fg_color="transparent")
        bottom_grid.pack(fill="x", padx=14, pady=8)
        bottom_grid.columnconfigure(0, weight=3)
        bottom_grid.columnconfigure(1, weight=4)

        # Left 4-Column Stat Tiles
        tiles_frame = ctk.CTkFrame(bottom_grid, fg_color="transparent")
        tiles_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        tiles_frame.columnconfigure((0, 1), weight=1)

        # Ping Tile
        p_tile = ctk.CTkFrame(tiles_frame, fg_color=COLOR_SURFACE_ALT, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        p_tile.grid(row=0, column=0, padx=2, pady=2, sticky="nsew")
        ctk.CTkLabel(p_tile, text="PING", font=ctk.CTkFont(size=9, weight="bold"), text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=8, pady=(3, 0))
        self.lat_lbl = ctk.CTkLabel(p_tile, text="-- ms", font=ctk.CTkFont(family="Consolas", size=12, weight="bold"), text_color=COLOR_CYAN)
        self.lat_lbl.pack(anchor="w", padx=8, pady=(0, 3))

        # Total Data Tile
        d_tile = ctk.CTkFrame(tiles_frame, fg_color=COLOR_SURFACE_ALT, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        d_tile.grid(row=0, column=1, padx=2, pady=2, sticky="nsew")
        ctk.CTkLabel(d_tile, text="SESSION DATA", font=ctk.CTkFont(size=9, weight="bold"), text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=8, pady=(3, 0))
        self.total_data_lbl = ctk.CTkLabel(d_tile, text="0.0 MB", font=ctk.CTkFont(family="Consolas", size=12, weight="bold"), text_color=COLOR_TEXT)
        self.total_data_lbl.pack(anchor="w", padx=8, pady=(0, 3))

        # Download Tile
        down_tile = ctk.CTkFrame(tiles_frame, fg_color=COLOR_SURFACE_ALT, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        down_tile.grid(row=1, column=0, padx=2, pady=2, sticky="nsew")
        ctk.CTkLabel(down_tile, text="DOWNLOAD", font=ctk.CTkFont(size=9, weight="bold"), text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=8, pady=(3, 0))
        self.down_lbl = ctk.CTkLabel(down_tile, text="0.0 KB/s", font=ctk.CTkFont(family="Consolas", size=12, weight="bold"), text_color=COLOR_EMERALD)
        self.down_lbl.pack(anchor="w", padx=8, pady=(0, 3))

        # Upload Tile
        up_tile = ctk.CTkFrame(tiles_frame, fg_color=COLOR_SURFACE_ALT, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        up_tile.grid(row=1, column=1, padx=2, pady=2, sticky="nsew")
        ctk.CTkLabel(up_tile, text="UPLOAD", font=ctk.CTkFont(size=9, weight="bold"), text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=8, pady=(3, 0))
        self.up_lbl = ctk.CTkLabel(up_tile, text="0.0 KB/s", font=ctk.CTkFont(family="Consolas", size=12, weight="bold"), text_color=COLOR_CYAN)
        self.up_lbl.pack(anchor="w", padx=8, pady=(0, 3))

        # Right Rolling Traffic Waveform Canvas
        graph_box = ctk.CTkFrame(bottom_grid, fg_color=COLOR_SURFACE_ALT, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        graph_box.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        graph_top = ctk.CTkFrame(graph_box, fg_color="transparent")
        graph_top.pack(fill="x", padx=8, pady=(4, 1))

        ctk.CTkLabel(graph_top, text="LIVE TRAFFIC WAVEFORM", font=ctk.CTkFont(size=8, weight="bold"), text_color=COLOR_TEXT_DIM).pack(side="left")
        ctk.CTkLabel(graph_top, text="🟢 DL  🔵 UL", font=ctk.CTkFont(size=8, weight="bold"), text_color=COLOR_TEXT_MUTED).pack(side="right")

        self.traffic_canvas = tk.Canvas(graph_box, height=48, bg=COLOR_SURFACE_ALT, highlightthickness=0)
        self.traffic_canvas.pack(fill="both", expand=True, padx=6, pady=(0, 4))

    # =============================================================
    # ANIMATION ENGINE (Canvas Radar Rings, Waveform & Route Pipe)
    # =============================================================
    def _start_animation_loop(self):
        def tick():
            if not getattr(self, "_is_running", True):
                return

            self._pulse_phase += 0.06
            if self._pulse_phase > 2 * math.pi:
                self._pulse_phase -= 2 * math.pi

            self._draw_radar_pulse()
            self._draw_route_pipeline()
            self._draw_traffic_waveform()

            self.after(35, tick)

        self.after(50, tick)

    def _draw_radar_pulse(self):
        self.radar_canvas.delete("all")
        cx, cy = 105, 95
        state = self.engine.state

        if state == STATE_CONNECTED:
            ring_color = "#047857"
            max_r = 92
        elif state == STATE_CONNECTING:
            ring_color = "#B45309"
            max_r = 88
        elif state == STATE_ERROR:
            ring_color = "#991B1B"
            max_r = 84
        else:
            ring_color = "#1E2A44"
            max_r = 78

        for i in range(2):
            phase = (self._pulse_phase + i * math.pi) % (2 * math.pi)
            factor = (math.sin(phase) + 1.0) / 2.0
            r = 60 + factor * (max_r - 60)
            self.radar_canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline=ring_color, width=1)

    def _draw_route_pipeline(self):
        self.route_canvas.delete("all")
        w = self.route_canvas.winfo_width()
        h = self.route_canvas.winfo_height()
        if w < 10:
            return

        cy = h // 2
        state = self.engine.state

        pipe_color = COLOR_BORDER
        glow_color = COLOR_SURFACE_ALT
        dot_color = COLOR_TEXT_DIM

        if state == STATE_CONNECTED:
            pipe_color = "#064E3B"
            glow_color = "#059669"
            dot_color = COLOR_EMERALD
        elif state == STATE_CONNECTING:
            pipe_color = "#451A03"
            glow_color = "#D97706"
            dot_color = COLOR_AMBER

        self.route_canvas.create_line(10, cy, w - 10, cy, fill=pipe_color, width=4, capstyle="round")

        if state in (STATE_CONNECTED, STATE_CONNECTING):
            self._route_dot_pos = (self._route_dot_pos + 4.0) % max(1, w - 20)
            dot_x = 10 + self._route_dot_pos
            self.route_canvas.create_oval(dot_x - 8, cy - 8, dot_x + 8, cy + 8, fill=glow_color, outline="")
            self.route_canvas.create_oval(dot_x - 4, cy - 4, dot_x + 4, cy + 4, fill=dot_color, outline="")

    def _draw_traffic_waveform(self):
        self.traffic_canvas.delete("all")
        w = self.traffic_canvas.winfo_width()
        h = self.traffic_canvas.winfo_height()
        if w < 10 or h < 10:
            return

        # Grid guidelines
        self.traffic_canvas.create_line(0, h // 2, w, h // 2, fill="#162035", width=1, dash=(2, 4))

        points_down = []
        points_up = []
        max_val = max(max(self.down_history), max(self.up_history), 50.0)

        n = len(self.down_history)
        step_x = w / max(n - 1, 1)

        for idx in range(n):
            x = idx * step_x
            y_down = (h - 4) - (self.down_history[idx] / max_val) * (h - 10)
            y_up = (h - 4) - (self.up_history[idx] / max_val) * (h - 10)
            points_down.extend([x, y_down])
            points_up.extend([x, y_up])

        if len(points_down) >= 4:
            self.traffic_canvas.create_line(points_down, fill=COLOR_EMERALD, width=2, smooth=True)
        if len(points_up) >= 4:
            self.traffic_canvas.create_line(points_up, fill=COLOR_CYAN, width=1, dash=(2, 2), smooth=True)

    # =============================================================
    # INTERACTION & STATE CONTROLS
    # =============================================================
    def _on_server_select(self, choice: str):
        clean_choice = re.sub(r"\s*\[\d+\s*ms\]", "", choice).strip()
        self.route_dst_loc.configure(text=clean_choice.split("(")[0].strip())

    def _on_kill_switch_toggle(self):
        enabled = self.kill_switch_var.get()
        settings_mgr.set("kill_switch_enabled", enabled)
        self.engine.set_kill_switch(enabled)

    def _on_minimized_toggle(self):
        enabled = self.minimize_to_tray_var.get()
        settings_mgr.set("start_minimized", enabled)

    def _on_startup_toggle(self):
        val = self.startup_var.get()
        set_windows_startup(val, start_minimized=self.minimize_to_tray_var.get())
        settings_mgr.set("start_with_windows", val)

    def _on_auto_connect_toggle(self):
        val = self.auto_connect_var.get()
        settings_mgr.set("auto_connect_on_launch", val)

    def _on_sound_fx_toggle(self):
        val = self.sound_fx_var.get()
        settings_mgr.set("sound_effects", val)
        if val:
            play_connect()

    def _on_ad_block_toggle(self):
        val = self.ad_block_var.get()
        settings_mgr.set("ad_blocker", val)

    def _on_malware_toggle(self):
        val = self.malware_var.get()
        settings_mgr.set("malware_shield", val)

    def _on_split_tunnel_toggle(self):
        val = self.split_enabled_var.get()
        settings_mgr.set("split_tunneling_enabled", val)

    def _on_split_app_toggle(self, exe_name: str, var):
        apps = set(a.lower() for a in settings_mgr.get("split_tunnel_apps", []))
        if var.get():
            apps.add(exe_name.lower())
        else:
            apps.discard(exe_name.lower())
        settings_mgr.set("split_tunnel_apps", list(apps))

    def _add_custom_split_app(self):
        app = self.custom_app_entry.get().strip()
        if not app:
            return
        if not app.endswith(".exe"):
            app += ".exe"
        apps = set(a.lower() for a in settings_mgr.get("split_tunnel_apps", []))
        apps.add(app.lower())
        settings_mgr.set("split_tunnel_apps", list(apps))
        self.custom_app_entry.delete(0, "end")
        messagebox.showinfo("Split Tunneling", f"Excluded '{app}' from VPN tunnel. Connect/reconnect to apply.")

    def _run_leak_audit(self):
        self.audit_score_lbl.configure(text="STATUS: Running Audit...", text_color=COLOR_AMBER)
        self.audit_btn.configure(state="disabled")

        def task():
            res = run_leak_test()
            self.safe_after(0, lambda: self._apply_audit_results(res))

        threading.Thread(target=task, daemon=True).start()

    def _apply_audit_results(self, res: dict):
        self.audit_btn.configure(state="normal")
        self.audit_ip_lbl.configure(text=f"Public IP: {res.get('ip', 'Unknown')}", text_color=COLOR_TEXT)
        self.audit_loc_lbl.configure(text=f"Location: {res.get('country', 'Unknown')} ({res.get('isp', '')})", text_color=COLOR_TEXT_MUTED)
        self.audit_dns_lbl.configure(text=f"DNS Resolver: {res.get('dns_server', 'DoH Cloudflare')}", text_color=COLOR_CYAN)

        if res.get("ipv6_leaking"):
            self.audit_ipv6_lbl.configure(text=f"IPv6: LEAK DETECTED ({res.get('ipv6_address')})", text_color=COLOR_RED)
            self.audit_score_lbl.configure(text="STATUS: ⚠️ WARNING (IPv6 Leaking)", text_color=COLOR_AMBER)
        else:
            self.audit_ipv6_lbl.configure(text="IPv6 Leak: 0% (Strict IPv4 Shielded)", text_color=COLOR_EMERALD)
            self.audit_score_lbl.configure(text="STATUS: 🔒 100% SECURE (Audited)", text_color="#34D399")

    def _import_custom_node(self):
        link = self.custom_uri_entry.get().strip()
        if not link.startswith("vless://"):
            messagebox.showerror("Invalid Link", "Please enter a valid vless:// connection link.")
            return

        node = import_custom_vless(link)
        if node:
            self.custom_uri_entry.delete(0, "end")
            self._refresh_nodes_dropdown()
            messagebox.showinfo("Success", f"Node '{node['name']}' imported successfully!")
        else:
            messagebox.showerror("Error", "Failed to parse VLESS configuration link.")

    def _parse_interval(self, text: str) -> int:
        try:
            num = int(text.split()[0])
            return num * 60
        except Exception:
            return 300

    def _parse_scope(self, text: str) -> str:
        return "same_region" if "Same Region" in text else "global"

    def _on_auto_rotate_toggle(self):
        enabled = self.auto_rotate_var.get()
        settings_mgr.set("auto_rotate_enabled", enabled)
        interval = self._parse_interval(self.rotate_interval_menu.get())
        scope = self._parse_scope(self.rotate_scope_menu.get())
        self.engine.set_auto_rotate(enabled, interval, scope=scope)
        if not enabled:
            self.rotation_label.configure(text="🔄 IP: OFF", text_color=COLOR_TEXT_DIM)
        else:
            if self.engine.state == STATE_CONNECTED:
                self.rotation_label.configure(text=f"🔄 IP: {self.engine.get_rotation_countdown_str()}", text_color=COLOR_PURPLE)
            else:
                self.rotation_label.configure(text="🔄 IP: Ready", text_color=COLOR_TEXT_MUTED)

    def _on_rotation_interval_change(self, choice: str):
        interval = self._parse_interval(choice)
        enabled = self.auto_rotate_var.get()
        scope = self._parse_scope(self.rotate_scope_menu.get())
        self.engine.set_auto_rotate(enabled, interval, scope=scope)

    def _on_rotation_scope_change(self, choice: str):
        scope = self._parse_scope(choice)
        self.engine.set_rotation_scope(scope)

    def _on_ip_rotated(self, new_node_name: str):
        self.safe_after(0, lambda: self.status_subtitle.configure(
            text=f"Rotated IP: {new_node_name}", text_color=COLOR_PURPLE
        ))
        self.safe_after(600, lambda: threading.Thread(target=self._refresh_ip_info, daemon=True).start())
        if hasattr(self, "tray_manager") and self.tray_manager:
            scope_desc = "Same-Region" if getattr(self.engine, "rotation_scope", "") == "same_region" else "Global"
            self.tray_manager.notify(f"Zero-Downtime IP Rotated to: {new_node_name} ({scope_desc})", "XION VPN (Seamless IP Hop)")

    def _refresh_ip_info(self):
        data = get_public_ip_info()
        self.current_ip_info = data
        self.after(0, lambda: self._update_ip_labels(data))

    def _update_ip_labels(self, data: dict):
        ip = data.get("ip", "Unknown")
        city = data.get("city", "")
        country = data.get("country", "")
        isp = data.get("isp", "")
        loc = f"{city}, {country}".strip(", ")
        if isp:
            loc += f" ({isp})"

        if self.engine.state == STATE_CONNECTED:
            self.route_dst_ip.configure(text=ip)
            self.route_dst_loc.configure(text=loc or "Protected Node")
        else:
            self.route_src_ip.configure(text=ip)
            self.route_src_loc.configure(text=loc or "Local ISP")
            self.route_dst_ip.configure(text="Shield Inactive")
            self.route_dst_loc.configure(text="Tap Power to Connect")

    def _toggle_connection(self):
        if self.engine.state == STATE_CONNECTED:
            threading.Thread(target=self.engine.disconnect, daemon=True).start()
        elif self.engine.state in (STATE_DISCONNECTED, STATE_ERROR):
            selected_tab = self.side_tabs.get()

            def _do_connect():
                if self.engine.state == STATE_ERROR:
                    self.engine.disconnect()
                    time.sleep(0.5)

                if selected_tab == "🌐 Custom":
                    host = self.vps_host.get().strip() or "127.0.0.1"
                    try:
                        port = int(self.vps_port.get().strip())
                    except ValueError:
                        self.safe_after(0, lambda: messagebox.showerror("Error", "Invalid port number."))
                        return
                    password = self.vps_pass.get().strip()
                    self.engine.connect_xion_server(host, port, password)
                else:
                    raw_selected = self.server_dropdown.get()
                    clean_selected = re.sub(r"\s*\[\d+\s*ms\]", "", raw_selected).strip()

                    selected_node = None
                    for n in self.available_nodes:
                        if n["name"] == clean_selected:
                            selected_node = n
                            break

                    if not selected_node:
                        selected_node = self.available_nodes[0]

                    if "Auto" in selected_node["name"] or "Smart Connect" in selected_node["name"]:
                        self.engine.connect_smart_auto()
                    else:
                        self.engine.connect_node(selected_node["uri"], selected_node["name"])

            threading.Thread(target=_do_connect, daemon=True).start()

    def _on_engine_state_change(self, state: str, message: str):
        self.safe_after(0, lambda: self._update_ui_state(state, message))

    def _update_ui_state(self, state: str, message: str):
        if state == STATE_CONNECTED:
            self.power_btn.configure(fg_color="#047857", hover_color="#065F46", text_color="#FFFFFF")
            self.status_title.configure(text="PROTECTED & SHIELDED", text_color=COLOR_EMERALD)
            self.status_subtitle.configure(text=message or "Encrypted Tunnel Active", text_color="#34D399")
            self.stats_tracker.reset()
            self.safe_after(1200, lambda: threading.Thread(target=self._refresh_ip_info, daemon=True).start())

        elif state == STATE_CONNECTING:
            self.power_btn.configure(fg_color="#78350F", hover_color="#92400E", text_color="#FDE68A")
            self.status_title.configure(text="SHIELDING...", text_color=COLOR_AMBER)
            self.status_subtitle.configure(text=message or "Establishing secure tunnel...", text_color=COLOR_AMBER)
            if getattr(self.engine, "_is_rotating", False):
                self.rotation_label.configure(text="🔄 IP: Rotating...", text_color=COLOR_PURPLE)

        elif state == STATE_DISCONNECTED:
            self.power_btn.configure(fg_color="#1E293B", hover_color="#334155", text_color="#38BDF8")
            self.status_title.configure(text="DISCONNECTED", text_color=COLOR_TEXT_MUTED)
            self.status_subtitle.configure(text=message or "Tap power hub to activate encrypted shield", text_color=COLOR_TEXT_DIM)
            self.duration_label.configure(text="⏱️ 00:00:00")
            self.rotation_label.configure(
                text="🔄 IP: Ready" if self.engine.auto_rotate_enabled else "🔄 IP: OFF",
                text_color=COLOR_TEXT_DIM
            )
            self.route_dst_ip.configure(text="Shield Inactive")
            self.route_dst_loc.configure(text="Tap Power to Connect")
            self.safe_after(1000, lambda: threading.Thread(target=self._refresh_ip_info, daemon=True).start())

        elif state == STATE_ERROR:
            self.power_btn.configure(fg_color="#7F1D1D", hover_color="#991B1B", text_color="#FCA5A5")
            self.status_title.configure(text="SHIELD HALTED", text_color=COLOR_RED)
            self.status_subtitle.configure(text=message[:55] if message else "Connection error", text_color=COLOR_RED)
            self.rotation_label.configure(
                text="🔄 IP: Ready" if self.engine.auto_rotate_enabled else "🔄 IP: OFF",
                text_color=COLOR_TEXT_DIM
            )
            self.route_dst_ip.configure(text="Shield Inactive")
            self.route_dst_loc.configure(text="Tap Power to Retry")

        if hasattr(self, "tray_manager") and self.tray_manager:
            self.tray_manager.update_status(state, message)

    def hide_to_tray(self):
        """Hides the main window to the system tray while keeping the VPN running in background."""
        self.withdraw()
        if hasattr(self, "tray_manager") and self.tray_manager:
            if self.engine.state == STATE_CONNECTED:
                node = self.engine.connected_node_name or "Secure Node"
                self.tray_manager.notify(f"Protected via {node}. App minimized to tray.", "XION VPN")
            else:
                self.tray_manager.notify("XION VPN is running silently in system tray.", "XION VPN")

    def show_window(self):
        """Restores and brings the main window to the foreground."""
        self.deiconify()
        self.state("normal")
        self.lift()
        self.focus_force()
        try:
            self.attributes("-topmost", True)
            self.after(250, lambda: self.attributes("-topmost", False))
        except Exception:
            pass

    def toggle_connection_from_tray(self):
        self._toggle_connection()

    def quit_application(self):
        self._is_running = False
        if self.engine.state in (STATE_CONNECTED, STATE_CONNECTING):
            self.engine.disconnect()
        if hasattr(self, "tray_manager") and self.tray_manager:
            self.tray_manager.stop()
        try:
            self.quit()
        except Exception:
            pass
        self.destroy()

    def on_close(self):
        if getattr(self, "minimize_to_tray_var", None) and self.minimize_to_tray_var.get():
            self.hide_to_tray()
        else:
            self.quit_application()

    def _start_background_loops(self):
        self._is_running = True

        def loop():
            counter = 0
            while getattr(self, "_is_running", True):
                time.sleep(1.0)
                counter += 1

                try:
                    if self.engine.state == STATE_CONNECTED:
                        dur_str = f"⏱️ {self.engine.get_duration_str()}"
                        self.safe_after(0, lambda d=dur_str: self.duration_label.configure(text=d))

                    rot_str = f"🔄 IP: {self.engine.get_rotation_countdown_str()}"
                    rot_color = COLOR_PURPLE if (self.engine.auto_rotate_enabled and self.engine.state == STATE_CONNECTED) else COLOR_TEXT_DIM
                    self.safe_after(0, lambda r=rot_str, c=rot_color: self.rotation_label.configure(text=r, text_color=c))

                    stats = self.stats_tracker.update()
                    down_kbs = stats['down_speed_kbs']
                    up_kbs = stats['up_speed_kbs']

                    self.down_history.append(down_kbs)
                    self.up_history.append(up_kbs)

                    down_str = f"{down_kbs:.1f} KB/s" if down_kbs < 1000 else f"{down_kbs/1024:.1f} MB/s"
                    up_str = f"{up_kbs:.1f} KB/s" if up_kbs < 1000 else f"{up_kbs/1024:.1f} MB/s"

                    # Accumulate session data and persist to settings
                    bytes_this_sec = int((down_kbs + up_kbs) * 1024)
                    self.total_bytes_transferred += bytes_this_sec
                    if self.engine.state == STATE_CONNECTED:
                        settings_mgr.add_data_usage(bytes_this_sec)

                    tot_mb = self.total_bytes_transferred / (1024 * 1024)
                    tot_str = f"{tot_mb:.1f} MB" if tot_mb < 1024 else f"{tot_mb/1024:.2f} GB"

                    self.safe_after(0, lambda ds=down_str, us=up_str, ts=tot_str: (
                        self.down_lbl.configure(text=ds),
                        self.up_lbl.configure(text=us),
                        self.total_data_lbl.configure(text=ts)
                    ))

                    # Measure ping every 4 seconds
                    if counter % 4 == 0:
                        lat = measure_latency("1.1.1.1")
                        lat_str = f"{lat} ms" if lat > 0 else "-- ms"
                        self.safe_after(0, lambda l=lat_str: self.lat_lbl.configure(text=l))

                    # Update monthly usage label every 10 seconds
                    if counter % 10 == 0 and hasattr(self, "history_data_lbl"):
                        tot_gb = settings_mgr.get("total_data_bytes", 0) / (1024 * 1024 * 1024)
                        mo_gb = settings_mgr.get("monthly_data_bytes", 0) / (1024 * 1024 * 1024)
                        self.safe_after(0, lambda t=tot_gb, m=mo_gb: self.history_data_lbl.configure(
                            text=f"Total: {t:.2f} GB | This Month: {m:.2f} GB"
                        ))

                    # Update node pings every 30 seconds
                    if counter % 30 == 0:
                        threading.Thread(target=self._ping_check_routine, daemon=True).start()

                except Exception:
                    break

        threading.Thread(target=loop, daemon=True).start()

if __name__ == "__main__":
    app = XionVpnApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
