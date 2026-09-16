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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SINGBOX_EXE = os.path.join(BASE_DIR, "sing-box.exe")
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

    def set_kill_switch(self, enabled: bool):
        """Enable or disable the VPN Kill Switch."""
        self.kill_switch_enabled = enabled
        if not enabled and self.kill_switch_blocking:
            self.kill_switch_blocking = False
            set_windows_system_proxy(False)
            set_env_proxy(False)
            self._set_state(STATE_DISCONNECTED, "Kill Switch released. Internet restored.")

    def _start_watchdog(self):
        """Monitors singbox process. If it crashes while Kill Switch is active, blocks internet."""
        def monitor():
            while self.state == STATE_CONNECTED and self.singbox_process:
                time.sleep(1.0)
                if self.singbox_process and self.singbox_process.poll() is not None:
                    if not self._user_initiated_disconnect:
                        print("[vpn_engine] WARNING: VPN process dropped unexpectedly!")
                        if self.kill_switch_enabled:
                            self.kill_switch_blocking = True
                            # Point proxy to dead port 127.0.0.1:1 to immediately block all internet access
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
        elif state == STATE_DISCONNECTED:
            self.connected_time = None

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

        admin = is_admin()
        mode_desc = "Full-System VPN (All Apps)" if admin else "Standard Mode"
        self._set_state(STATE_CONNECTING, f"Connecting to {node_name} ({mode_desc})...")
        self._user_initiated_disconnect = False
        self.kill_switch_blocking = False

        # Terminate any existing core
        self._kill_singbox()

        # Build and write configuration (TUN enabled if Administrator)
        cfg = build_singbox_config(outbound, local_port=10808, enable_tun=admin)
        with open(ACTIVE_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

        # Launch sing-box in background with no terminal window
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            self.singbox_process = subprocess.Popen(
                [SINGBOX_EXE, "run", "-c", ACTIVE_CONFIG_PATH],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creationflags
            )
            time.sleep(1.2)

            if self.singbox_process.poll() is not None:
                _, err = self.singbox_process.communicate()
                err_text = err.decode("utf-8", errors="ignore").strip()
                
                # If TUN mode failed (e.g. non-admin, Wintun permissions), fallback immediately to Standard Proxy mode
                if admin:
                    print(f"[vpn_engine] TUN mode start failed ({err_text[:60]}). Falling back to Standard Mode...")
                    admin = False
                    cfg = build_singbox_config(outbound, local_port=10808, enable_tun=False)
                    with open(ACTIVE_CONFIG_PATH, "w", encoding="utf-8") as f:
                        json.dump(cfg, f, indent=2)

                    self.singbox_process = subprocess.Popen(
                        [SINGBOX_EXE, "run", "-c", ACTIVE_CONFIG_PATH],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        creationflags=creationflags
                    )
                    time.sleep(1.2)
                    if self.singbox_process.poll() is not None:
                        _, err = self.singbox_process.communicate()
                        err_text = err.decode("utf-8", errors="ignore").strip()
                        self._set_state(STATE_ERROR, f"Core failed: {err_text[:80]}")
                        return False
                else:
                    self._set_state(STATE_ERROR, f"Core failed: {err_text[:80]}")
                    return False

            # Configure Windows System Proxy & Developer Env Proxy (OpenCode, VS Code, Git)
            set_windows_system_proxy(True, "127.0.0.1", 10808)
            set_env_proxy(True, "127.0.0.1", 10808)

            # Quick verification test
            self._verify_tunnel(timeout=4)

            self.active_engine = "singbox_node"
            self.connected_node_name = node_name
            self.is_tun_active = admin
            status_tag = "Full System (All Apps)" if admin else "Browsers & Dev Tools"
            self._set_state(STATE_CONNECTED, f"Protected via {node_name} [{status_tag}]")

            # Start watchdog to protect connection with Kill Switch
            self._start_watchdog()
            return True

        except Exception as e:
            self._set_state(STATE_ERROR, f"Connection error: {e}")
            self.disconnect()
            return False

    def connect_smart_auto(self) -> bool:
        """Tries fast global nodes sequentially until one connects successfully."""
        self._set_state(STATE_CONNECTING, "Selecting fastest available server...")
        nodes = fetch_live_nodes()

        for node in nodes:
            name = node.get("name", "Fast Node")
            uri = node.get("uri", "")
            if not uri or "Auto-Select" in name:
                continue

            self._set_state(STATE_CONNECTING, f"Testing {name}...")
            if self.connect_node(uri, name):
                return True

        # Fallback to first regular builtin node
        fallback = BUILTIN_FAST_NODES[1] if len(BUILTIN_FAST_NODES) > 1 else BUILTIN_FAST_NODES[0]
        return self.connect_node(fallback["uri"], fallback["name"])

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
