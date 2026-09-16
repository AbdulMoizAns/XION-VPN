"""
sys_utils.py - Windows System, Network & Proxy Utilities for XION VPN
"""
import ctypes
import os
import socket
import time
import winreg
import requests
import psutil

# Windows Internet Option Constants
INTERNET_OPTION_SETTINGS_CHANGED = 39
INTERNET_OPTION_REFRESH = 37

def is_admin() -> bool:
    """Check if the current process is running with Administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def restart_as_admin():
    """Restarts current application with Administrator privileges via UAC prompt."""
    import sys
    if not is_admin():
        if getattr(sys, "frozen", False):
            # Running as compiled standalone .exe
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, "", None, 1)
        else:
            # Running as Python script
            script = os.path.abspath(sys.argv[0])
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}"', None, 1)
        sys.exit(0)

def set_env_proxy(enable: bool, host: str = "127.0.0.1", port: int = 10808):
    """
    Sets or unsets HTTP_PROXY and HTTPS_PROXY for developer tools (OpenCode, VS Code, Git, Node, Python).
    Updates current process and Windows User Environment in Registry.
    """
    proxy_url = f"http://{host}:{port}"
    if enable:
        os.environ["HTTP_PROXY"] = proxy_url
        os.environ["HTTPS_PROXY"] = proxy_url
        os.environ["ALL_PROXY"] = f"socks5://{host}:{port}"
    else:
        for var in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]:
            os.environ.pop(var, None)

    try:
        env_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_WRITE)
        if enable:
            winreg.SetValueEx(env_key, "HTTP_PROXY", 0, winreg.REG_SZ, proxy_url)
            winreg.SetValueEx(env_key, "HTTPS_PROXY", 0, winreg.REG_SZ, proxy_url)
        else:
            try:
                winreg.DeleteValue(env_key, "HTTP_PROXY")
            except FileNotFoundError:
                pass
            try:
                winreg.DeleteValue(env_key, "HTTPS_PROXY")
            except FileNotFoundError:
                pass
        winreg.CloseKey(env_key)
    except Exception:
        pass

def refresh_windows_internet_options():
    """Notify Windows system that internet/proxy settings have changed."""
    try:
        wininet = ctypes.windll.wininet
        wininet.InternetSetOptionW(0, INTERNET_OPTION_SETTINGS_CHANGED, 0, 0)
        wininet.InternetSetOptionW(0, INTERNET_OPTION_REFRESH, 0, 0)
    except Exception as e:
        print(f"[sys_utils] Error refreshing Windows internet options: {e}")

def set_windows_system_proxy(enable: bool, host: str = "127.0.0.1", port: int = 10808):
    reg_key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_key_path, 0, winreg.KEY_WRITE)
        if enable:
            proxy_addr = f"http={host}:{port};https={host}:{port};socks={host}:{port}"
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, proxy_addr)
            winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, "<local>")
        else:
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
        winreg.CloseKey(key)
        refresh_windows_internet_options()
        return True
    except Exception as e:
        print(f"[sys_utils] Failed to set registry proxy: {e}")
        return False

def get_current_proxy_status() -> bool:
    """Check if Windows proxy is currently enabled."""
    reg_key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_key_path, 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, "ProxyEnable")
        winreg.CloseKey(key)
        return bool(val)
    except Exception:
        return False

def get_public_ip_info() -> dict:
    """
    Fetches the current external IP and Geo-location information.
    Uses multiple fallback endpoints for maximum reliability.
    """
    endpoints = [
        "https://ipapi.co/json/",
        "http://ip-api.com/json/?fields=status,message,country,countryCode,city,query,org",
        "https://api.ipify.org?format=json"
    ]

    for url in endpoints:
        try:
            resp = requests.get(url, timeout=3.5)
            if resp.status_code == 200:
                data = resp.json()
                if "query" in data:  # ip-api.com format
                    return {
                        "ip": data.get("query", "Unknown"),
                        "country": data.get("country", "Unknown"),
                        "country_code": data.get("countryCode", "UN"),
                        "city": data.get("city", "Unknown"),
                        "isp": data.get("org", "Unknown")
                    }
                elif "ip" in data:  # ipapi.co or ipify format
                    return {
                        "ip": data.get("ip", "Unknown"),
                        "country": data.get("country_name", data.get("country", "Protected")),
                        "country_code": data.get("country_code", "OK"),
                        "city": data.get("city", "Cloud"),
                        "isp": data.get("org", "Secure Network")
                    }
        except Exception:
            continue

    return {
        "ip": "Offline / Protected",
        "country": "Unknown",
        "country_code": "UN",
        "city": "Unknown",
        "isp": "Unknown"
    }

def measure_latency(host: str = "1.1.1.1", port: int = 53, timeout: float = 2.0) -> int:
    """
    Measures latency in milliseconds to a fast target DNS server.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        start = time.perf_counter()
        s.connect((host, port))
        end = time.perf_counter()
        s.close()
        return max(1, int((end - start) * 1000))
    except Exception:
        return -1

class NetworkStatsTracker:
    """Tracks live download/upload speeds and total data transfer."""
    def __init__(self):
        self.initial_bytes_recv = 0
        self.initial_bytes_sent = 0
        self.last_bytes_recv = 0
        self.last_bytes_sent = 0
        self.last_time = time.time()
        self.reset()

    def reset(self):
        counters = psutil.net_io_counters()
        self.initial_bytes_recv = counters.bytes_recv
        self.initial_bytes_sent = counters.bytes_sent
        self.last_bytes_recv = counters.bytes_recv
        self.last_bytes_sent = counters.bytes_sent
        self.last_time = time.time()

    def update(self) -> dict:
        counters = psutil.net_io_counters()
        now = time.time()
        dt = max(0.001, now - self.last_time)

        diff_recv = max(0, counters.bytes_recv - self.last_bytes_recv)
        diff_sent = max(0, counters.bytes_sent - self.last_bytes_sent)

        # Speeds in KB/s
        down_speed_kbs = (diff_recv / dt) / 1024.0
        up_speed_kbs = (diff_sent / dt) / 1024.0

        # Total session transfer in MB
        total_recv_mb = (counters.bytes_recv - self.initial_bytes_recv) / (1024.0 * 1024.0)
        total_sent_mb = (counters.bytes_sent - self.initial_bytes_sent) / (1024.0 * 1024.0)

        self.last_bytes_recv = counters.bytes_recv
        self.last_bytes_sent = counters.bytes_sent
        self.last_time = now

        return {
            "down_speed_kbs": down_speed_kbs,
            "up_speed_kbs": up_speed_kbs,
            "total_recv_mb": max(0.0, total_recv_mb),
            "total_sent_mb": max(0.0, total_sent_mb),
        }
