"""
vpn_engine.py - Core Multi-Engine VPN Controller for XION VPN
Supports standalone sing-box core (zero drivers/install needed), Windows system proxy, and custom VPS mode.
"""
import json
import os
import subprocess
import threading
import time
import requests
from sys_utils import set_windows_system_proxy, set_env_proxy, is_admin
from tunnel_client import XionTunnelClient
from node_manager import parse_vless_uri, build_singbox_config, fetch_live_nodes, BUILTIN_FAST_NODES

STATE_DISCONNECTED = "DISCONNECTED"
STATE_CONNECTING = "CONNECTING"
STATE_CONNECTED = "CONNECTED"
STATE_ERROR = "ERROR"

import sys

def get_app_dir() -> str:
    """Returns directory containing executable or script."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_bundle_dir() -> str:
    """Returns PyInstaller internal _MEIPASS bundle dir, or app dir."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return get_app_dir()

BASE_DIR = get_app_dir()
BUNDLE_DIR = get_bundle_dir()

def find_singbox_exe() -> str:
    candidates = [
        os.path.join(BUNDLE_DIR, "sing-box.exe"),
        os.path.join(BASE_DIR, "sing-box.exe"),
        os.path.join(os.path.dirname(BASE_DIR), "sing-box.exe"),
        os.path.join(BASE_DIR, "src", "sing-box.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return os.path.join(BASE_DIR, "sing-box.exe")

SINGBOX_EXE = find_singbox_exe()
ACTIVE_CONFIG_PATH = os.path.join(BASE_DIR, "active_config.json")

class VpnEngine:
    def __init__(self):
        self.state = STATE_DISCONNECTED
        self.active_engine = None
        self.singbox_process = None
        self.tunnel_client = None
        self.on_state_change = None  # Callback: fn(state, msg)
        self.connected_time = None
        self.connected_node_name = ""
        self.is_tun_active = False

        # Kill Switch Security
        self.kill_switch_enabled = False
        self.kill_switch_blocking = False
        self._user_initiated_disconnect = False

        # Auto-Rotate IP / Dynamic Server Hopping
        self.auto_rotate_enabled = False
        self.auto_rotate_interval = 300  # 5 minutes (300 seconds)
        self.rotation_scope = "same_region"  # "same_region" or "global"
        self._last_rotation_time = None
        self._is_rotating = False
        self.on_ip_rotated = None  # Callback: fn(new_node_name)
        self._rotation_monitor_started = False

        # Watchdog ID: each new connection gets a unique ID.
        # The watchdog thread only fires if its ID still matches the current one.
        self._watchdog_id = 0

        # Log file handle — stored so we can close it before next session
        self._log_file = None

        # Clean slate on startup: clear any lingering processes or proxy locks
        self._kill_singbox()
        set_windows_system_proxy(False)
        set_env_proxy(False)

        # Start background rotation monitor loop
        self._start_rotation_monitor()

    def set_kill_switch(self, enabled: bool):
        """Enable or disable the VPN Kill Switch."""
        self.kill_switch_enabled = enabled
        if not enabled and self.kill_switch_blocking:
            self.kill_switch_blocking = False
            set_windows_system_proxy(False)
            set_env_proxy(False)
            self._set_state(STATE_DISCONNECTED, "Kill Switch released. Internet restored.")

    def _start_watchdog(self):
        """Monitors singbox process. If it crashes while Kill Switch is active, blocks internet.
        Uses a watchdog_id snapshot so any previous zombie watchdog thread is automatically
        invalidated when a new connection is established."""
        self._watchdog_id += 1
        my_id = self._watchdog_id

        def monitor():
            # Grace period before monitoring begins — sing-box needs time to fully start
            time.sleep(2.5)
            while self._watchdog_id == my_id and self.state == STATE_CONNECTED and self.singbox_process:
                time.sleep(1.5)
                # Double-check ID again after sleeping so a disconnect during sleep doesn't false-fire
                if self._watchdog_id != my_id:
                    break
                if self.singbox_process and self.singbox_process.poll() is not None:
                    if not self._user_initiated_disconnect and not self._is_rotating and self._watchdog_id == my_id:
                        print(f"[vpn_engine] WARNING: VPN process dropped unexpectedly! (watchdog#{my_id})")
                        if self.kill_switch_enabled:
                            self.kill_switch_blocking = True
                            # Point proxy to dead port 127.0.0.1:1 to block all unencrypted traffic
                            set_windows_system_proxy(True, "127.0.0.1", 1)
                            set_env_proxy(True, "127.0.0.1", 1)
                            self._set_state(STATE_ERROR, "KILL SWITCH ENGAGED! Internet blocked to prevent IP leak.")
                        else:
                            self.disconnect()
                    break
        threading.Thread(target=monitor, daemon=True).start()

    def _set_state(self, state: str, message: str = ""):
        self.state = state
        if state == STATE_CONNECTED:
            self.connected_time = time.time()
            if not self._is_rotating:
                self._last_rotation_time = time.time()
        elif state == STATE_DISCONNECTED:
            self.connected_time = None
            self._last_rotation_time = None

        if self.on_state_change:
            self.on_state_change(state, message)

    def connect_node(self, uri: str, node_name: str = "Secure Node") -> bool:
        """Connects via embedded sing-box core. Uses Full-System TUN mode if Admin."""
        if not os.path.isfile(SINGBOX_EXE):
            self._set_state(STATE_ERROR, "sing-box.exe not found in app directory.")
            return False

        outbound = parse_vless_uri(uri)
        if not outbound:
            self._set_state(STATE_ERROR, "Failed to parse server configuration.")
            return False

        # Find if this node is in the multi-node pool
        nodes = fetch_live_nodes()
        target_node = None
        for n in nodes:
            if n.get("name") == node_name or n.get("uri") == uri:
                target_node = n
                break

        # Zero-downtime hot-switch if sing-box is already running
        if (
            self.state == STATE_CONNECTED
            and self.active_engine == "singbox_node"
            and self.singbox_process
            and self.singbox_process.poll() is None
            and target_node
        ):
            print(f"[vpn_engine] Sing-box active, executing zero-downtime hot-switch to {node_name}...")
            if self.hot_switch_node(target_node):
                return True

        admin = is_admin()
        mode_desc = "Full-System VPN (All Apps)" if admin else "Standard Mode"
        self._set_state(STATE_CONNECTING, f"Connecting to {node_name} ({mode_desc})...")
        self._user_initiated_disconnect = False
        self.kill_switch_blocking = False

        # Terminate any lingering core to free ports
        self._kill_singbox()

        # Build and write configuration (TUN enabled if Administrator)
        # Pre-load all multi-nodes for instantaneous hot-switching via Clash API
        multi_pool = [n for n in nodes if n.get("uri") and "Auto-Select" not in n.get("name", "")]
        default_tag = target_node.get("tag") if target_node else "proxy-out"
        cfg = build_singbox_config(outbound, local_port=10808, enable_tun=admin, multi_nodes=multi_pool, default_tag=default_tag)
        with open(ACTIVE_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

        # Log sing-box output to disk to avoid pipe deadlock on Windows
        log_path = os.path.join(BASE_DIR, "singbox.log")
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

        try:
            log_out = open(log_path, "w", encoding="utf-8")
            self._log_file = log_out  # track so _kill_singbox can close it
            self.singbox_process = subprocess.Popen(
                [SINGBOX_EXE, "run", "-c", ACTIVE_CONFIG_PATH],
                stdout=log_out,
                stderr=subprocess.STDOUT,
                creationflags=creationflags
            )
            time.sleep(1.2)

            if self.singbox_process.poll() is not None:
                log_out.close()
                self._log_file = None
                err_text = ""
                try:
                    with open(log_path, "r", encoding="utf-8", errors="ignore") as lf:
                        err_text = lf.read().strip()
                except Exception:
                    pass

                # If TUN mode failed, fallback immediately to Standard Proxy mode
                if admin:
                    print(f"[vpn_engine] TUN mode start failed ({err_text[:60]}). Falling back to Standard Mode...")
                    admin = False
                    cfg = build_singbox_config(outbound, local_port=10808, enable_tun=False, multi_nodes=multi_pool, default_tag=default_tag)
                    with open(ACTIVE_CONFIG_PATH, "w", encoding="utf-8") as f:
                        json.dump(cfg, f, indent=2)

                    log_out = open(log_path, "w", encoding="utf-8")
                    self._log_file = log_out  # update tracked handle
                    self.singbox_process = subprocess.Popen(
                        [SINGBOX_EXE, "run", "-c", ACTIVE_CONFIG_PATH],
                        stdout=log_out,
                        stderr=subprocess.STDOUT,
                        creationflags=creationflags
                    )
                    time.sleep(1.2)
                    if self.singbox_process.poll() is not None:
                        log_out.close()
                        self._set_state(STATE_ERROR, f"Core failed: {err_text[-120:] if err_text else 'Unknown startup error'}")
                        return False
                else:
                    self._set_state(STATE_ERROR, f"Core failed: {err_text[-120:] if err_text else 'Unknown startup error'}")
                    return False

            # Configure Windows System Proxy & Developer Env Proxy (OpenCode, VS Code, Git)
            set_windows_system_proxy(True, "127.0.0.1", 10808)
            set_env_proxy(True, "127.0.0.1", 10808)

            # Quick verification test - must actually pass traffic before declaring connected!
            if not self._verify_tunnel(timeout=4):
                print(f"[vpn_engine] Tunnel verification failed for {node_name}")
                set_windows_system_proxy(False)
                set_env_proxy(False)
                self._kill_singbox()
                self._set_state(STATE_ERROR, f"Server {node_name} is unreachable or timed out.")
                return False

            self.active_engine = "singbox_node"
            self.connected_node_name = node_name
            self.is_tun_active = admin
            status_tag = "Full System (All Apps)" if admin else "Browsers & Dev Tools"
            self._set_state(STATE_CONNECTED, f"Protected via {node_name} [{status_tag}]")

            # Start watchdog to protect connection with Kill Switch
            self._start_watchdog()
            return True

        except Exception as e:
            set_windows_system_proxy(False)
            set_env_proxy(False)
            self._kill_singbox()
            self._set_state(STATE_ERROR, f"Connection error: {e}")
            return False

    def connect_smart_auto(self) -> bool:
        """Tries fast global nodes sequentially until one connects and verifies successfully."""
        self._set_state(STATE_CONNECTING, "Selecting fastest available server...")
        nodes = fetch_live_nodes()

        for node in nodes:
            name = node.get("name", "Fast Node")
            uri = node.get("uri", "")
            if not uri or "Auto-Select" in name:
                continue

            self._set_state(STATE_CONNECTING, f"Connecting to {name}...")
            if self.connect_node(uri, name):
                return True

        # If all nodes fail
        self._set_state(STATE_ERROR, "No responding servers available. Please check internet connection.")
        return False

    def _verify_tunnel(self, timeout: int = 3) -> bool:
        """Verifies if proxy port 10808 is responding and passing HTTP traffic."""
        proxies = {"http": "http://127.0.0.1:10808", "https": "http://127.0.0.1:10808"}
        try:
            r = requests.get("http://cp.cloudflare.com/generate_204", proxies=proxies, timeout=timeout)
            return r.status_code in (200, 204)
        except Exception:
            try:
                r = requests.get("https://api.ipify.org?format=json", proxies=proxies, timeout=timeout)
                return r.status_code == 200
            except Exception:
                return False

    def connect_xion_server(self, host: str, port: int, password: str) -> bool:
        """Connects to custom Python VPS server using AES-256-GCM."""
        self._set_state(STATE_CONNECTING, f"Connecting to XION VPS ({host}:{port})...")
        local_port = 10808
        self._kill_singbox()

        try:
            self.tunnel_client = XionTunnelClient(host, port, password, local_port=local_port)
            self.tunnel_client.start()
            time.sleep(0.5)

            set_windows_system_proxy(True, "127.0.0.1", local_port)
            self.active_engine = "xion_vps"
            self.connected_node_name = "Private VPS"
            self._set_state(STATE_CONNECTED, "Protected by Private XION Server")
            return True
        except Exception as e:
            self._set_state(STATE_ERROR, f"Failed to connect: {e}")
            self.disconnect()
            return False

    def _kill_singbox(self):
        """Terminates active sing-box instance and kills any orphan processes holding ports."""
        # Invalidate any running watchdog thread immediately
        self._watchdog_id += 1

        # Close log file handle first so Windows can overwrite it next session
        if self._log_file:
            try:
                self._log_file.close()
            except Exception:
                pass
            self._log_file = None

        if self.singbox_process:
            try:
                self.singbox_process.terminate()
                self.singbox_process.wait(timeout=1.0)
            except Exception:
                try:
                    self.singbox_process.kill()
                except Exception:
                    pass
            self.singbox_process = None

        # Clean up any orphaned sing-box.exe processes to ensure port 10808 is completely free
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/IM", "sing-box.exe"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.run(["pkill", "-9", "-f", "sing-box"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def disconnect(self):
        """Cleanly disconnects tunnel, terminates processes, and restores Windows proxy."""
        if self.state == STATE_DISCONNECTED:
            return

        self._user_initiated_disconnect = True
        self.kill_switch_blocking = False
        self._set_state(STATE_CONNECTING, "Disconnecting & Restoring Windows Settings...")

        # Turn off Windows proxy & environment variables immediately
        set_windows_system_proxy(False)
        set_env_proxy(False)

        # Terminate sing-box
        self._kill_singbox()

        # Stop Python tunnel client if active
        if self.tunnel_client:
            self.tunnel_client.stop()
            self.tunnel_client = None

        self.active_engine = None
        self.connected_node_name = ""
        self.is_tun_active = False
        self._set_state(STATE_DISCONNECTED, "Disconnected")

    def get_duration_str(self) -> str:
        """Returns formatted connection time HH:MM:SS."""
        if not self.connected_time or self.state != STATE_CONNECTED:
            return "00:00:00"
        elapsed = int(time.time() - self.connected_time)
        hrs = elapsed // 3600
        mins = (elapsed % 3600) // 60
        secs = elapsed % 60
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"

    def set_auto_rotate(self, enabled: bool, interval_seconds: int = 300, scope: str = "same_region"):
        """Enable or disable dynamic IP rotation with scope setting ('same_region' or 'global')."""
        self.auto_rotate_enabled = enabled
        self.auto_rotate_interval = max(10, interval_seconds)
        self.rotation_scope = scope
        if enabled and self.state == STATE_CONNECTED:
            self._last_rotation_time = time.time()

    def set_rotation_scope(self, scope: str):
        """Sets rotation scope to 'same_region' or 'global'."""
        self.rotation_scope = scope

    def hot_switch_node(self, target_node: dict) -> bool:
        """
        Hot-switches active outbound via local sing-box Clash API (127.0.0.1:9090).
        Execution time: < 20ms. Zero process restart, zero TUN drop, zero disconnection.
        """
        tag = target_node.get("tag") or target_node.get("name")
        node_name = target_node.get("name") or tag
        try:
            s = requests.Session()
            s.trust_env = False
            r = s.put("http://127.0.0.1:9090/proxies/proxy-out", json={"name": tag}, timeout=2.0)
            if r.status_code in (200, 204):
                print(f"[vpn_engine] Hot-switched successfully to {node_name} ({tag})")
                self.connected_node_name = node_name
                self._last_rotation_time = time.time()
                admin = self.is_tun_active
                status_tag = "Full System (All Apps)" if admin else "Browsers & Dev Tools"
                self._set_state(STATE_CONNECTED, f"Protected via {node_name} [{status_tag}]")
                if self.on_ip_rotated:
                    try:
                        self.on_ip_rotated(node_name)
                    except Exception:
                        pass
                return True
        except Exception as e:
            print(f"[vpn_engine] Clash API hot-switch error: {e}")
        return False

    def get_rotation_countdown_seconds(self) -> int:
        """Returns remaining seconds until next automatic IP rotation."""
        if not self.auto_rotate_enabled or self.state != STATE_CONNECTED or not self._last_rotation_time:
            return 0
        elapsed = time.time() - self._last_rotation_time
        return max(0, int(self.auto_rotate_interval - elapsed))

    def get_rotation_countdown_str(self) -> str:
        """Returns formatted countdown MM:SS or status string."""
        if not self.auto_rotate_enabled:
            return "OFF"
        if self.state != STATE_CONNECTED:
            return "Ready"
        if self._is_rotating:
            return "Rotating..."
        rem = self.get_rotation_countdown_seconds()
        mins = rem // 60
        secs = rem % 60
        return f"{mins:02d}:{secs:02d}"

    def rotate_to_next_node(self) -> bool:
        """Seamlessly hops to the next server in the pool to rotate IP (Zero-Downtime)."""
        if self.state != STATE_CONNECTED or self._is_rotating:
            return False

        nodes = fetch_live_nodes()
        valid_nodes = [n for n in nodes if n.get("uri") and "Auto-Select" not in n.get("name", "")]
        if not valid_nodes:
            return False

        # Find current node
        curr_node = None
        for n in valid_nodes:
            if n.get("name") == self.connected_node_name:
                curr_node = n
                break

        curr_country = curr_node.get("country", "") if curr_node else ""

        if self.rotation_scope == "same_region" and curr_country:
            # Filter pool to the SAME country/region, excluding currently connected node
            same_region_nodes = [n for n in valid_nodes if n.get("country") == curr_country and n.get("name") != self.connected_node_name]
            if same_region_nodes:
                target_node = same_region_nodes[0]
            else:
                # If only 1 node exists in this country, fallback to other nodes
                other_nodes = [n for n in valid_nodes if n.get("name") != self.connected_node_name]
                target_node = other_nodes[0] if other_nodes else valid_nodes[0]
        else:
            # Global hop across countries
            other_nodes = [n for n in valid_nodes if n.get("country") != curr_country]
            if not other_nodes:
                other_nodes = [n for n in valid_nodes if n.get("name") != self.connected_node_name]
            target_node = other_nodes[0] if other_nodes else valid_nodes[0]

        print(f"[vpn_engine] Rotating IP ({self.rotation_scope}): {self.connected_node_name} -> {target_node['name']}")
        self._is_rotating = True
        try:
            # 1. Zero-downtime hot-switch via Clash API (< 20ms, zero dropped packets)
            if self.singbox_process and self.singbox_process.poll() is None:
                if self.hot_switch_node(target_node):
                    self._is_rotating = False
                    return True

            # 2. Fallback: standard connect if sing-box API is not responding
            self._set_state(STATE_CONNECTING, f"Rotating IP to {target_node['name']}...")
            success = self.connect_node(target_node["uri"], target_node["name"])
            self._is_rotating = False
            if success:
                self._last_rotation_time = time.time()
                if self.on_ip_rotated:
                    try:
                        self.on_ip_rotated(target_node["name"])
                    except Exception:
                        pass
                return True
            else:
                print("[vpn_engine] Rotation target failed, falling back to smart auto...")
                recovered = self.connect_smart_auto()
                if recovered:
                    self._last_rotation_time = time.time()
                    if self.on_ip_rotated:
                        try:
                            self.on_ip_rotated(self.connected_node_name)
                        except Exception:
                            pass
                    return True
                return False
        except Exception as e:
            self._is_rotating = False
            print(f"[vpn_engine] Error during IP rotation: {e}")
            return False

    def _start_rotation_monitor(self):
        """Background thread that tracks rotation interval and triggers node hopping."""
        if getattr(self, "_rotation_monitor_started", False):
            return
        self._rotation_monitor_started = True

        def _monitor():
            while True:
                time.sleep(1.0)
                try:
                    if (
                        self.auto_rotate_enabled
                        and self.state == STATE_CONNECTED
                        and not self._is_rotating
                        and self._last_rotation_time
                    ):
                        elapsed = time.time() - self._last_rotation_time
                        if elapsed >= self.auto_rotate_interval:
                            print(f"[vpn_engine] Rotation interval ({self.auto_rotate_interval}s) reached. Triggering IP hop...")
                            threading.Thread(target=self.rotate_to_next_node, daemon=True).start()
                except Exception as e:
                    print(f"[vpn_engine] Rotation monitor error: {e}")

        threading.Thread(target=_monitor, daemon=True).start()
