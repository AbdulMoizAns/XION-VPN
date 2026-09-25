"""
XION VPN - Persistent Settings Manager
Stores and manages user preferences in %APPDATA%/XION-VPN/settings.json
"""

import json
import os
import sys

DEFAULT_SETTINGS = {
    "start_with_windows": False,
    "start_minimized": False,
    "auto_connect_on_launch": False,
    "sound_effects": True,
    "ad_blocker": True,
    "malware_shield": True,
    "split_tunneling_enabled": False,
    "split_tunnel_apps": ["steam.exe", "epicgameslauncher.exe", "discord.exe"],
    "double_vpn_enabled": False,
    "double_vpn_entry": "sg-fast",
    "double_vpn_exit": "de-frankfurt",
    "rotation_interval": 5,
    "rotation_scope": "same_region",
    "preferred_node": "auto",
    "total_data_bytes": 0,
    "monthly_data_bytes": 0,
    "last_month_reset": "",
}

class SettingsManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SettingsManager, cls).__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        # Choose appdata folder or fallback to base directory
        appdata = os.environ.get("APPDATA")
        if appdata:
            self.config_dir = os.path.join(appdata, "XION-VPN")
        else:
            self.config_dir = os.path.dirname(os.path.abspath(__file__))
        
        os.makedirs(self.config_dir, exist_ok=True)
        self.config_file = os.path.join(self.config_dir, "settings.json")
        self.settings = dict(DEFAULT_SETTINGS)
        self.load()

    def load(self):
        if os.path.isfile(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        # Merge with defaults to ensure all keys exist
                        for k, v in data.items():
                            self.settings[k] = v
            except Exception as e:
                print(f"[SettingsManager] Error loading settings: {e}")
        else:
            self.save()

    def save(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"[SettingsManager] Error saving settings: {e}")

    def get(self, key, default=None):
        return self.settings.get(key, default if default is not None else DEFAULT_SETTINGS.get(key))

    def set(self, key, value):
        self.settings[key] = value
        self.save()

    def update(self, dict_values):
        self.settings.update(dict_values)
        self.save()

    def add_data_usage(self, byte_count):
        if byte_count <= 0:
            return
        total = self.settings.get("total_data_bytes", 0) + byte_count
        monthly = self.settings.get("monthly_data_bytes", 0) + byte_count
        self.settings["total_data_bytes"] = total
        self.settings["monthly_data_bytes"] = monthly
        # Save periodically
        self.save()

# Global Singleton
settings_mgr = SettingsManager()
