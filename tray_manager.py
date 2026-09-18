"""
tray_manager.py - System Tray (Notification Area) Manager for XION VPN
Enables running XION VPN in the background with quick tray controls,
live status updates, and balloon notifications.
"""
import os
import sys
import threading
from PIL import Image
import pystray
from pystray import MenuItem as item, Menu


def get_icon_path() -> str:
    """Resolves app_icon.ico path for both development and PyInstaller bundled builds."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundle_path = os.path.join(sys._MEIPASS, "app_icon.ico")
        if os.path.isfile(bundle_path):
            return bundle_path
        app_dir = os.path.dirname(sys.executable)
        exe_icon = os.path.join(app_dir, "app_icon.ico")
        if os.path.isfile(exe_icon):
            return exe_icon

    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "app_icon.ico")


class TrayManager:
    def __init__(self, app):
        self.app = app
        self.icon = None
        self._thread = None
        self._is_running = False

    def _get_status_label(self, _) -> str:
        state = self.app.engine.state
        if state == "CONNECTED":
            node = self.app.engine.connected_node_name or "Secure Server"
            return f"🛡️ Protected ({node})"
        elif state == "CONNECTING":
            return "⚡ Connecting..."
        elif state == "ERROR":
            return "⚠️ Shield Halted"
        return "⭕ Status: Disconnected"

    def _get_action_label(self, _) -> str:
        if self.app.engine.state == "CONNECTED":
            return "Disconnect VPN"
        return "Connect VPN"

    def _on_open_clicked(self, icon, item):
        """Restores and focuses the main application window."""
        self.app.safe_after(0, self.app.show_window)

    def _on_toggle_clicked(self, icon, item):
        """Toggles VPN connection from system tray."""
        self.app.safe_after(0, self.app.toggle_connection_from_tray)

    def _on_exit_clicked(self, icon, item):
        """Cleanly disconnects VPN and terminates the entire application."""
        self.app.safe_after(0, self.app.quit_application)

    def _build_menu(self) -> Menu:
        return Menu(
            item("Open XION VPN", self._on_open_clicked, default=True),
            Menu.SEPARATOR,
            item(self._get_status_label, None, enabled=False),
            item(self._get_action_label, self._on_toggle_clicked),
            Menu.SEPARATOR,
            item("Exit XION VPN", self._on_exit_clicked)
        )

    def start(self):
        """Initializes and runs system tray icon in detached background loop."""
        icon_path = get_icon_path()
        try:
            if os.path.isfile(icon_path):
                img = Image.open(icon_path)
            else:
                # Fallback to simple colored square if icon file is missing
                img = Image.new("RGBA", (64, 64), color=(0, 240, 255, 255))
        except Exception:
            img = Image.new("RGBA", (64, 64), color=(0, 240, 255, 255))

        self.icon = pystray.Icon(
            "XION-VPN",
            img,
            "XION VPN - Autonomous Privacy Workstation",
            menu=self._build_menu()
        )

        try:
            self.icon.run_detached()
            self._is_running = True
        except Exception as e:
            print(f"[tray_manager] Failed to start detached tray: {e}")
            self._is_running = False

    def update_status(self, state: str, message: str = ""):
        """Updates tooltip and tray menu when connection status changes."""
        if not self.icon:
            return

        tooltip = "XION VPN"
        if state == "CONNECTED":
            node = self.app.engine.connected_node_name or "Secure Server"
            tooltip = f"XION VPN - Protected ({node})"
        elif state == "CONNECTING":
            tooltip = "XION VPN - Connecting..."
        elif state == "ERROR":
            tooltip = "XION VPN - Shield Halted"
        else:
            tooltip = "XION VPN - Disconnected"

        try:
            self.icon.title = tooltip
            self.icon.update_menu()
        except Exception:
            pass

    def notify(self, message: str, title: str = "XION VPN"):
        """Displays native Windows tray notification."""
        if self.icon and self._is_running:
            try:
                self.icon.notify(message, title)
            except Exception:
                pass

    def stop(self):
        """Stops tray icon and cleans up resources."""
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None
            self._is_running = False
