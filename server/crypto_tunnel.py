"""
crypto_tunnel.py - AES-256-GCM Encrypted Socket Framing for XION VPN
Provides authenticated encryption for TCP streams between XION Client and Server.
"""
import os
import struct
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SALT = b"XION_VPN_SECURE_SALT_v1"

def derive_aes_key(password: str) -> bytes:
    """Derives a 256-bit AES key from a passphrase using PBKDF2-HMAC-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=SALT,
        iterations=100_000,
    )
    return kdf.derive(password.encode("utf-8"))

class EncryptedSocket:
    """Wraps a standard socket with AES-256-GCM authenticated encryption."""
    def __init__(self, sock, key: bytes):
        self.sock = sock
        self.aesgcm = AESGCM(key)

    def send_packet(self, data: bytes):
        """Encrypts and transmits a data packet."""
        if not data:
            return
        nonce = os.urandom(12)  # 96-bit unique nonce for GCM
        ciphertext = self.aesgcm.encrypt(nonce, data, None)
        # Frame: [4 bytes payload length][12 bytes nonce][ciphertext]
        header = struct.pack("!I", len(ciphertext))
        self.sock.sendall(header + nonce + ciphertext)

    def recv_packet(self) -> bytes:
        """Receives and decrypts a data packet. Returns empty bytes on EOF/disconnect."""
        header = self._recv_exact(4)
        if not header:
            return b""
        payload_len = struct.unpack("!I", header)[0]
        if payload_len > 10 * 1024 * 1024:  # Sanity check 10MB limit
            raise ValueError(f"Packet too large: {payload_len} bytes")

        nonce = self._recv_exact(12)
        if not nonce:
            return b""

        ciphertext = self._recv_exact(payload_len)
        if not ciphertext:
            return b""

        return self.aesgcm.decrypt(nonce, ciphertext, None)

    def _recv_exact(self, n: int) -> bytes:
        """Reads exactly n bytes from socket."""
        buf = bytearray()
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                return b""
            buf.extend(chunk)
        return bytes(buf)

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass
