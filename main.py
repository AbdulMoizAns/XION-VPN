"""
main.py - Entry Point for XION VPN Desktop Application
"""
import sys
import os

# Ensure local directory is in Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui import XionVpnApp

def main():
    app = XionVpnApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()

if __name__ == "__main__":
    main()
