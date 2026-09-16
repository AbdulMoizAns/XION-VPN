"""
gui.py - Beast-Mode Widescreen Landscape Dashboard for XION VPN
Built with CustomTkinter for Windows.
Features:
- Widescreen 960x620 Cyberpunk Workstation Layout
- Canvas-based Animated Pulsing Power Hub & Radar Rings
- Live Rolling Traffic Waveforms (Download & Upload Sparklines)
- Interactive End-to-End Tunnel Route Visualizer
- Real-time Multi-Metric Telemetry (Ping, Speeds, Session Volume)
- Military-Grade Security Controls (DoH 1.1.1.1, IPv6 Shield, Kill Switch)
"""
import math
import os
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
    set_windows_system_proxy
)
from vpn_engine import (
    VpnEngine,
    STATE_DISCONNECTED,
    STATE_CONNECTING,
    STATE_CONNECTED,
    STATE_ERROR
)
from node_manager import fetch_live_nodes, BUILTIN_FAST_NODES

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
    def __init__(self):
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
        self.stats_tracker = NetworkStatsTracker()

        # State data
        self.available_nodes = BUILTIN_FAST_NODES
        self.current_ip_info = {"ip": "Fetching...", "country": "...", "city": "...", "isp": "..."}
        self.initial_real_ip = "Fetching..."
        self.initial_real_country = "Local ISP"
        self._is_running = True

        # Animation & Telemetry states
        self._pulse_phase = 0.0
        self._route_dot_pos = 0.0
        self.down_history = deque([0.0] * 30, maxlen=30)
        self.up_history = deque([0.0] * 30, maxlen=30)
        self.total_bytes_transferred = 0

        self._build_ui()
        self._start_animation_loop()
        self._start_background_loops()

        # Initial background load
        threading.Thread(target=self._initial_load, daemon=True).start()

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
        try:
            live = fetch_live_nodes()
            if live:
                self.available_nodes = live
                names = [n["name"] for n in self.available_nodes]
                self.safe_after(0, lambda: self.server_dropdown.configure(values=names))
        except Exception:
            pass

    def _build_ui(self):
        # Master Grid Layout (2 Columns: Left Sidebar [340px], Right Main Stage [620px])
        self.grid_columnconfigure(0, weight=0, minsize=340)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # =============================================================
        # LEFT SIDEBAR: Controls, Server Selector & Security Panel
        # =============================================================
        sidebar = ctk.CTkFrame(self, fg_color=COLOR_SIDEBAR, corner_radius=0, border_width=1, border_color=COLOR_BORDER)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        # 1. Header & Brand Box
        brand_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand_frame.pack(fill="x", padx=20, pady=(20, 12))

        brand_row = ctk.CTkFrame(brand_frame, fg_color="transparent")
        brand_row.pack(anchor="w")

        ctk.CTkLabel(
            brand_row,
            text="⚡ XION",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color="#FFFFFF"
        ).pack(side="left")

        ctk.CTkLabel(
            brand_row,
            text="VPN",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color=COLOR_CYAN
        ).pack(side="left", padx=(4, 8))

        # Mode Badge
        admin = is_admin()
        if admin:
            mode_badge = ctk.CTkLabel(
                brand_frame,
                text="🛡️ FULL-SYSTEM TUN",
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
                height=26,
                command=restart_as_admin
            )
            elevate_btn.pack(anchor="w", pady=(3, 0))

        # 2. Server Selection Card
        srv_card = ctk.CTkFrame(sidebar, fg_color=COLOR_SURFACE, corner_radius=14, border_width=1, border_color=COLOR_BORDER)
        srv_card.pack(fill="x", padx=16, pady=(8, 12))

        srv_title_row = ctk.CTkFrame(srv_card, fg_color="transparent")
        srv_title_row.pack(fill="x", padx=14, pady=(12, 6))

        ctk.CTkLabel(
            srv_title_row,
            text="LOCATION & ROUTE",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COLOR_TEXT_DIM
        ).pack(side="left")

        ctk.CTkLabel(
            srv_title_row,
            text="VLESS • DoH",
            font=ctk.CTkFont(family="Consolas", size=9, weight="bold"),
            text_color=COLOR_CYAN,
            fg_color="#0F1F38",
            corner_radius=4,
            padx=6,
            pady=2
        ).pack(side="right")

        self.server_dropdown = ctk.CTkOptionMenu(
            srv_card,
            values=[n["name"] for n in self.available_nodes],
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=COLOR_SURFACE_ALT,
            button_color="#1E293B",
            button_hover_color="#334155",
            text_color="#FFFFFF",
            dropdown_fg_color=COLOR_SURFACE_ALT,
            dropdown_text_color="#FFFFFF",
            dropdown_hover_color="#1E293B",
            height=38,
            corner_radius=8,
            command=self._on_server_select
        )
        self.server_dropdown.set(self.available_nodes[0]["name"])
        self.server_dropdown.pack(fill="x", padx=14, pady=(0, 14))

        # 3. Sidebar Tabview (Security, Private VPS, Custom URI)
        side_tabs = ctk.CTkTabview(sidebar, fg_color=COLOR_SURFACE, corner_radius=12, border_width=1, border_color=COLOR_BORDER)
        side_tabs.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        tab_sec = side_tabs.add("🛡️ Security")
        tab_vps = side_tabs.add("🌐 VPS")
        tab_uri = side_tabs.add("🔗 URI")

        # Security Tab Contents
        sec_box = ctk.CTkFrame(tab_sec, fg_color="transparent")
        sec_box.pack(fill="both", expand=True, padx=4, pady=4)

        self.kill_switch_var = ctk.BooleanVar(value=False)
        self.ks_switch = ctk.CTkSwitch(
            sec_box,
            text="Active Kill Switch",
            font=ctk.CTkFont(size=12, weight="bold"),
            variable=self.kill_switch_var,
            onvalue=True,
            offvalue=False,
            command=self._on_kill_switch_toggle,
            progress_color=COLOR_EMERALD
        )
        self.ks_switch.pack(anchor="w", pady=(2, 2))

        ctk.CTkLabel(
            sec_box,
            text="Instantly blocks unencrypted traffic if tunnel disconnects unexpectedly.",
            font=ctk.CTkFont(size=10),
            text_color=COLOR_TEXT_DIM,
            wraplength=270,
            justify="left"
        ).pack(anchor="w", padx=(28, 0), pady=(0, 8))

        sec_badges = ctk.CTkFrame(sec_box, fg_color=COLOR_SURFACE_ALT, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        sec_badges.pack(fill="x", pady=4)

        ctk.CTkLabel(
            sec_badges,
            text="🔒 DoH DNS: Cloudflare 1.1.1.1 (Encrypted)",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COLOR_CYAN
        ).pack(anchor="w", padx=10, pady=(6, 2))

        ctk.CTkLabel(
            sec_badges,
            text="🛡️ IPv6 Leak Blocker: Active (IPv4 Only)",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COLOR_EMERALD
        ).pack(anchor="w", padx=10, pady=(2, 6))

        # VPS Tab Contents
        ctk.CTkLabel(tab_vps, text="Custom Python AES Server (server.py):", font=ctk.CTkFont(size=10), text_color=COLOR_TEXT_DIM).pack(anchor="w", pady=(2, 4))
        self.vps_host = ctk.CTkEntry(tab_vps, placeholder_text="VPS IP Address", height=28, fg_color=COLOR_SURFACE_ALT)
        self.vps_host.insert(0, "127.0.0.1")
        self.vps_host.pack(fill="x", pady=2)

        vps_row = ctk.CTkFrame(tab_vps, fg_color="transparent")
        vps_row.pack(fill="x", pady=2)
        self.vps_port = ctk.CTkEntry(vps_row, placeholder_text="8080", width=65, height=28, fg_color=COLOR_SURFACE_ALT)
        self.vps_port.insert(0, "8080")
        self.vps_port.pack(side="left", padx=(0, 4))
        self.vps_pass = ctk.CTkEntry(vps_row, placeholder_text="Password", show="*", height=28, fg_color=COLOR_SURFACE_ALT)
        self.vps_pass.insert(0, "xion_secret_pass_2026")
        self.vps_pass.pack(side="left", fill="x", expand=True)

        # URI Tab Contents
        ctk.CTkLabel(tab_uri, text="Paste raw vless:// configuration link:", font=ctk.CTkFont(size=10), text_color=COLOR_TEXT_DIM).pack(anchor="w", pady=(2, 4))
        self.custom_uri_entry = ctk.CTkEntry(tab_uri, placeholder_text="vless://uuid@host:port...", height=30, fg_color=COLOR_SURFACE_ALT)
        self.custom_uri_entry.pack(fill="x", pady=2)

        self.side_tabs = side_tabs

        # =============================================================
        # RIGHT MAIN STAGE: Route Visualizer, Animated Power Hub & Telemetry
        # =============================================================
        main_stage = ctk.CTkFrame(self, fg_color=COLOR_BG)
        main_stage.grid(row=0, column=1, sticky="nsew", padx=20, pady=16)
        main_stage.grid_rowconfigure(1, weight=1)
        main_stage.grid_columnconfigure(0, weight=1)

        # 1. TOP: End-to-End Tunnel Route Visualizer Card
        route_card = ctk.CTkFrame(main_stage, fg_color=COLOR_SURFACE, corner_radius=14, border_width=1, border_color=COLOR_BORDER)
        route_card.grid(row=0, column=0, sticky="ew", pady=(0, 12))

        route_inner = ctk.CTkFrame(route_card, fg_color="transparent")
        route_inner.pack(fill="x", padx=16, pady=12)

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
        hero_card = ctk.CTkFrame(main_stage, fg_color=COLOR_SURFACE, corner_radius=18, border_width=1, border_color=COLOR_BORDER)
        hero_card.grid(row=1, column=0, sticky="nsew", pady=(0, 12))
        hero_card.grid_columnconfigure(0, weight=1)
        hero_card.grid_rowconfigure(0, weight=1)

        hub_container = ctk.CTkFrame(hero_card, fg_color="transparent")
        hub_container.place(relx=0.5, rely=0.5, anchor="center")

        # Canvas for animated radar pulsing circles
        self.radar_canvas = tk.Canvas(hub_container, width=220, height=220, bg=COLOR_SURFACE, highlightthickness=0)
        self.radar_canvas.pack()

        # Centered Circular Power Button inside Canvas
        self.power_btn = ctk.CTkButton(
            hub_container,
            text="⏻",
            font=ctk.CTkFont(size=46),
            fg_color="#1E293B",
            hover_color="#334155",
            text_color="#38BDF8",
            width=120,
            height=120,
            corner_radius=60,
            command=self._toggle_connection
        )
        self.power_btn.place(relx=0.5, rely=0.45, anchor="center")

        # Dynamic Status Title
        self.status_title = ctk.CTkLabel(
            hub_container,
            text="DISCONNECTED",
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
            text_color=COLOR_TEXT_MUTED
        )
        self.status_title.pack(pady=(4, 1))

        # Dynamic Status Subtitle
        self.status_subtitle = ctk.CTkLabel(
            hub_container,
            text="Tap power hub to activate encrypted shield",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_DIM
        )
        self.status_subtitle.pack(pady=(0, 4))

        # Session Timer Pill
        timer_pill = ctk.CTkFrame(hub_container, fg_color=COLOR_SURFACE_ALT, corner_radius=10, border_width=1, border_color=COLOR_BORDER)
        timer_pill.pack(pady=(2, 0))

        self.duration_label = ctk.CTkLabel(
            timer_pill,
            text="⏱️ 00:00:00",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color=COLOR_CYAN,
            padx=14,
            pady=3
        )
        self.duration_label.pack()

        # 3. BOTTOM: Telemetry Strip & Real-Time Rolling Waveform Card
        bottom_card = ctk.CTkFrame(main_stage, fg_color=COLOR_SURFACE, corner_radius=14, border_width=1, border_color=COLOR_BORDER)
        bottom_card.grid(row=2, column=0, sticky="ew", pady=(0, 0))

        bottom_grid = ctk.CTkFrame(bottom_card, fg_color="transparent")
        bottom_grid.pack(fill="x", padx=16, pady=10)
        bottom_grid.columnconfigure(0, weight=3)
        bottom_grid.columnconfigure(1, weight=4)

        # Left 4-Column Stat Tiles
        tiles_frame = ctk.CTkFrame(bottom_grid, fg_color="transparent")
        tiles_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        tiles_frame.columnconfigure((0, 1), weight=1)

        # Ping Tile
        p_tile = ctk.CTkFrame(tiles_frame, fg_color=COLOR_SURFACE_ALT, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        p_tile.grid(row=0, column=0, padx=3, pady=3, sticky="nsew")
        ctk.CTkLabel(p_tile, text="PING", font=ctk.CTkFont(size=9, weight="bold"), text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=8, pady=(4, 0))
        self.lat_lbl = ctk.CTkLabel(p_tile, text="-- ms", font=ctk.CTkFont(family="Consolas", size=13, weight="bold"), text_color=COLOR_CYAN)
        self.lat_lbl.pack(anchor="w", padx=8, pady=(0, 4))

        # Total Data Tile
        d_tile = ctk.CTkFrame(tiles_frame, fg_color=COLOR_SURFACE_ALT, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        d_tile.grid(row=0, column=1, padx=3, pady=3, sticky="nsew")
        ctk.CTkLabel(d_tile, text="SESSION DATA", font=ctk.CTkFont(size=9, weight="bold"), text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=8, pady=(4, 0))
        self.total_data_lbl = ctk.CTkLabel(d_tile, text="0.0 MB", font=ctk.CTkFont(family="Consolas", size=13, weight="bold"), text_color=COLOR_TEXT)
        self.total_data_lbl.pack(anchor="w", padx=8, pady=(0, 4))

        # Download Tile
        down_tile = ctk.CTkFrame(tiles_frame, fg_color=COLOR_SURFACE_ALT, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        down_tile.grid(row=1, column=0, padx=3, pady=3, sticky="nsew")
        ctk.CTkLabel(down_tile, text="DOWNLOAD", font=ctk.CTkFont(size=9, weight="bold"), text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=8, pady=(4, 0))
        self.down_lbl = ctk.CTkLabel(down_tile, text="0.0 KB/s", font=ctk.CTkFont(family="Consolas", size=13, weight="bold"), text_color=COLOR_EMERALD)
        self.down_lbl.pack(anchor="w", padx=8, pady=(0, 4))

        # Upload Tile
        up_tile = ctk.CTkFrame(tiles_frame, fg_color=COLOR_SURFACE_ALT, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        up_tile.grid(row=1, column=1, padx=3, pady=3, sticky="nsew")
        ctk.CTkLabel(up_tile, text="UPLOAD", font=ctk.CTkFont(size=9, weight="bold"), text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=8, pady=(4, 0))
        self.up_lbl = ctk.CTkLabel(up_tile, text="0.0 KB/s", font=ctk.CTkFont(family="Consolas", size=13, weight="bold"), text_color=COLOR_CYAN)
        self.up_lbl.pack(anchor="w", padx=8, pady=(0, 4))

        # Right Rolling Traffic Waveform Canvas
        graph_box = ctk.CTkFrame(bottom_grid, fg_color=COLOR_SURFACE_ALT, corner_radius=10, border_width=1, border_color=COLOR_BORDER)
        graph_box.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        graph_top = ctk.CTkFrame(graph_box, fg_color="transparent")
        graph_top.pack(fill="x", padx=10, pady=(6, 2))

        ctk.CTkLabel(graph_top, text="LIVE TRAFFIC WAVEFORM", font=ctk.CTkFont(size=9, weight="bold"), text_color=COLOR_TEXT_DIM).pack(side="left")
        ctk.CTkLabel(graph_top, text="🟢 DL  🔵 UL", font=ctk.CTkFont(size=9, weight="bold"), text_color=COLOR_TEXT_MUTED).pack(side="right")

        self.traffic_canvas = tk.Canvas(graph_box, height=52, bg=COLOR_SURFACE_ALT, highlightthickness=0)
        self.traffic_canvas.pack(fill="both", expand=True, padx=8, pady=(0, 6))

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
        cx, cy = 110, 100
        state = self.engine.state

        # Color choice based on engine state
        if state == STATE_CONNECTED:
            base_color = COLOR_EMERALD
            ring_color = "#047857"
            max_r = 95
        elif state == STATE_CONNECTING:
            base_color = COLOR_AMBER
            ring_color = "#B45309"
            max_r = 90
        elif state == STATE_ERROR:
            base_color = COLOR_RED
            ring_color = "#991B1B"
            max_r = 85
        else:
            base_color = COLOR_BORDER_LIGHT
            ring_color = "#1E2A44"
            max_r = 80

        # Draw 2 concentric pulsing wave rings
        for i in range(2):
            phase = (self._pulse_phase + i * math.pi) % (2 * math.pi)
            factor = (math.sin(phase) + 1.0) / 2.0  # 0.0 to 1.0
            r = 62 + factor * (max_r - 62)
            
            # Subtle line width oscillation
            w = 2 if state in (STATE_CONNECTED, STATE_CONNECTING) else 1
            color = base_color if factor > 0.4 else ring_color

            self.radar_canvas.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                outline=color,
                width=w
            )

        # Draw outer boundary halo ring
        self.radar_canvas.create_oval(
            cx - 62, cy - 62, cx + 62, cy + 62,
            outline=ring_color,
            width=2
        )

    def _draw_route_pipeline(self):
        self.route_canvas.delete("all")
        w = self.route_canvas.winfo_width()
        h = self.route_canvas.winfo_height()
        if w <= 10:
            return

        cy = h // 2
        # Base dotted connecting line
        line_color = COLOR_BORDER_LIGHT if self.engine.state == STATE_CONNECTED else COLOR_BORDER
        self.route_canvas.create_line(10, cy, w - 10, cy, fill=line_color, width=2, dash=(4, 4))

        # Center lock icon badge
        tag_color = COLOR_EMERALD if self.engine.state == STATE_CONNECTED else COLOR_TEXT_DIM
        self.route_canvas.create_text(w // 2, cy, text="🔒 256-bit DoH", fill=tag_color, font=("Consolas", 8, "bold"))

        # If connected or connecting, animate moving neon packet along line
        if self.engine.state in (STATE_CONNECTED, STATE_CONNECTING):
            self._route_dot_pos = (self._route_dot_pos + 3.0) % (w - 20)
            dot_x = 10 + self._route_dot_pos
            packet_color = COLOR_CYAN if self.engine.state == STATE_CONNECTED else COLOR_AMBER
            self.route_canvas.create_oval(dot_x - 3, cy - 3, dot_x + 3, cy + 3, fill=packet_color, outline="")

    def _draw_traffic_waveform(self):
        self.traffic_canvas.delete("all")
        w = self.traffic_canvas.winfo_width()
        h = self.traffic_canvas.winfo_height()
        if w <= 10 or h <= 10:
            return

        # Baseline
        self.traffic_canvas.create_line(0, h - 2, w, h - 2, fill=COLOR_BORDER, width=1)

        # Plot download points
        points_down = []
        points_up = []
        max_val = max(max(self.down_history), max(self.up_history), 50.0)

        n = len(self.down_history)
        step_x = w / max(n - 1, 1)

        for idx in range(n):
            x = idx * step_x
            # Normalize to canvas height
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
        # Update destination preview
        self.route_dst_loc.configure(text=choice.split("(")[0].strip())

    def _on_kill_switch_toggle(self):
        enabled = self.kill_switch_var.get()
        self.engine.set_kill_switch(enabled)

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
            if selected_tab == "🌐 VPS":
                host = self.vps_host.get().strip() or "127.0.0.1"
                try:
                    port = int(self.vps_port.get().strip())
                except ValueError:
                    messagebox.showerror("Error", "Invalid port number.")
                    return
                password = self.vps_pass.get().strip()
                threading.Thread(target=lambda: self.engine.connect_xion_server(host, port, password), daemon=True).start()
            elif selected_tab == "🔗 URI" and self.custom_uri_entry.get().strip().startswith("vless://"):
                uri = self.custom_uri_entry.get().strip()
                threading.Thread(target=lambda: self.engine.connect_node(uri, "Custom Node"), daemon=True).start()
            else:
                selected_name = self.server_dropdown.get()
                selected_node = None
                for n in self.available_nodes:
                    if n["name"] == selected_name:
                        selected_node = n
                        break

                if not selected_node:
                    selected_node = self.available_nodes[0]

                if "Auto-Select" in selected_node["name"]:
                    threading.Thread(target=self.engine.connect_smart_auto, daemon=True).start()
                else:
                    threading.Thread(target=lambda: self.engine.connect_node(selected_node["uri"], selected_node["name"]), daemon=True).start()

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

        elif state == STATE_DISCONNECTED:
            self.power_btn.configure(fg_color="#1E293B", hover_color="#334155", text_color="#38BDF8")
            self.status_title.configure(text="DISCONNECTED", text_color=COLOR_TEXT_MUTED)
            self.status_subtitle.configure(text="Tap power hub to activate encrypted shield", text_color=COLOR_TEXT_DIM)
            self.duration_label.configure(text="⏱️ 00:00:00")
            self.route_dst_ip.configure(text="Shield Inactive")
            self.route_dst_loc.configure(text="Tap Power to Connect")
            self.safe_after(1000, lambda: threading.Thread(target=self._refresh_ip_info, daemon=True).start())

        elif state == STATE_ERROR:
            self.power_btn.configure(fg_color="#7F1D1D", hover_color="#991B1B", text_color="#FCA5A5")
            self.status_title.configure(text="SHIELD HALTED", text_color=COLOR_RED)
            self.status_subtitle.configure(text=message[:45] if message else "Connection error", text_color=COLOR_RED)
            messagebox.showerror("VPN Error", message)

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

                    stats = self.stats_tracker.update()
                    down_kbs = stats['down_speed_kbs']
                    up_kbs = stats['up_speed_kbs']

                    self.down_history.append(down_kbs)
                    self.up_history.append(up_kbs)

                    down_str = f"{down_kbs:.1f} KB/s" if down_kbs < 1000 else f"{down_kbs/1024:.1f} MB/s"
                    up_str = f"{up_kbs:.1f} KB/s" if up_kbs < 1000 else f"{up_kbs/1024:.1f} MB/s"

                    # Calculate total session volume
                    self.total_bytes_transferred += int((down_kbs + up_kbs) * 1024)
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
                except Exception:
                    break

        threading.Thread(target=loop, daemon=True).start()

    def on_close(self):
        self._is_running = False
        if self.engine.state == STATE_CONNECTED:
            self.engine.disconnect()
        self.destroy()

if __name__ == "__main__":
    app = XionVpnApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()

