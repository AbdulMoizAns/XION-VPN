"""
XION VPN - Cyberpunk Sci-Fi Sound FX Engine
Provides lightweight futuristic audio feedback using Windows native winsound.
Non-blocking background execution ensures zero UI stutters.
"""

import threading
import sys

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

from settings_manager import settings_mgr

def _async_play(target, *args):
    if not HAS_WINSOUND:
        return
    if not settings_mgr.get("sound_effects", True):
        return
    t = threading.Thread(target=target, args=args, daemon=True)
    t.start()

def _beep_connect():
    try:
        # Futuristic ascending cyber chime (C5 -> E5 -> G5)
        winsound.Beep(523, 60)
        winsound.Beep(659, 60)
        winsound.Beep(784, 100)
    except Exception:
        pass

def _beep_disconnect():
    try:
        # Descending power-down tone
        winsound.Beep(784, 60)
        winsound.Beep(659, 60)
        winsound.Beep(440, 100)
    except Exception:
        pass

def _beep_rotate():
    try:
        # Subtle quick cyber frequency hop
        winsound.Beep(1046, 50)
        winsound.Beep(1318, 50)
    except Exception:
        pass

def _beep_alert():
    try:
        # Double warning pulse
        winsound.Beep(880, 80)
        winsound.Beep(600, 80)
    except Exception:
        pass

def play_connect():
    _async_play(_beep_connect)

def play_disconnect():
    _async_play(_beep_disconnect)

def play_rotate():
    _async_play(_beep_rotate)

def play_alert():
    _async_play(_beep_alert)
