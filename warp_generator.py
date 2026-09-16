"""
warp_generator.py - Cloudflare WARP WireGuard Profile Auto-Generator for XION VPN
Generates free, official, unlimited WireGuard configurations via Cloudflare API.
"""
import base64
import datetime
import json
import os
import requests
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization

CLOUDFLARE_API_URL = "https://api.cloudflareclient.com/v0a2158/reg"
DEFAULT_CONF_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "xion_warp.conf")

def generate_keypair() -> tuple[str, str]:
    """Generates a standard Curve25519 WireGuard private and public key in base64."""
    private_key = x25519.X25519PrivateKey.generate()
    public_key = private_key.public_key()

    priv_raw = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    pub_raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )

    priv_b64 = base64.b64encode(priv_raw).decode("utf-8")
    pub_b64 = base64.b64encode(pub_raw).decode("utf-8")
    return priv_b64, pub_b64

def register_warp_profile(output_path: str = DEFAULT_CONF_PATH) -> dict:
    """
    Registers a new device with Cloudflare WARP and generates a ready-to-use WireGuard configuration file.
    """
    priv_key, pub_key = generate_keypair()

    payload = {
        "key": pub_key,
        "install_id": "",
        "fcm_token": "",
        "tos": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "model": "PC",
        "serial_number": "",
        "locale": "en_US"
    }

    headers = {
        "User-Agent": "okhttp/3.12.1",
        "Content-Type": "application/json; charset=UTF-8"
    }

    resp = requests.post(CLOUDFLARE_API_URL, headers=headers, json=payload, timeout=10)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Cloudflare registration failed: HTTP {resp.status_code} - {resp.text}")

    data = resp.json()
    result = data.get("result") or data
    account = result.get("account", {})
    cfg = result.get("config", {})
    interface = cfg.get("interface", {})
    addresses = interface.get("addresses", {})
    v4 = addresses.get("v4", "172.16.0.2")
    v6 = addresses.get("v6", "")

    # Ensure subnet mask /32 for v4 and /128 for v6 if missing
    if "/" not in v4:
        v4 += "/32"
    if v6 and "/" not in v6:
        v6 += "/128"

    peers = cfg.get("peers", [])
    if peers:
        peer = peers[0]
        peer_pubkey = peer.get("public_key", "bmXOC+F1FxEMF9dyiK2H5/1SUtzH0JuVo51h2wPfgyo=")
        endpoint = peer.get("endpoint", {}).get("host", "engage.cloudflareclient.com:2408")
    else:
        peer_pubkey = "bmXOC+F1FxEMF9dyiK2H5/1SUtzH0JuVo51h2wPfgyo="
        endpoint = "engage.cloudflareclient.com:2408"

    address_line = f"{v4}, {v6}" if v6 else v4

    wireguard_conf = f"""[Interface]
PrivateKey = {priv_key}
Address = {address_line}
DNS = 1.1.1.1, 1.0.0.1

[Peer]
PublicKey = {peer_pubkey}
AllowedIPs = 0.0.0.0/0, ::/0
Endpoint = {endpoint}
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(wireguard_conf)

    return {
        "success": True,
        "conf_path": output_path,
        "ipv4": v4,
        "endpoint": endpoint,
        "license": account.get("license", ""),
        "account_type": account.get("account_type", "free")
    }

if __name__ == "__main__":
    print("Testing Cloudflare WARP Registration...")
    try:
        res = register_warp_profile()
        print("Success! Profile created at:", res["conf_path"])
        print("Assigned IP:", res["ipv4"])
        print("Endpoint:", res["endpoint"])
    except Exception as e:
        print("Error:", e)
