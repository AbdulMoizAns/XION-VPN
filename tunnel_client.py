"""
tunnel_client.py - Local Proxy Client for XION Encrypted Tunnel Mode
Accepts local connections (HTTP CONNECT / SOCKS5) from Windows apps and relays them
securely over an AES-256-GCM encrypted tunnel to a remote XION VPN server.
"""
import json
import socket
import threading
from crypto_tunnel import derive_aes_key, EncryptedSocket

class XionTunnelClient:
    def __init__(self, remote_server_host: str, remote_server_port: int, password: str, local_port: int = 10808):
        self.remote_server_host = remote_server_host
        self.remote_server_port = remote_server_port
        self.aes_key = derive_aes_key(password)
        self.local_port = local_port
        self.running = False
        self.server_sock = None
        self._thread = None

    def start(self):
        self.running = True
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind(("127.0.0.1", self.local_port))
        self.server_sock.listen(128)
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def _listen_loop(self):
        while self.running:
            try:
                client_sock, _ = self.server_sock.accept()
                t = threading.Thread(target=self._handle_client, args=(client_sock,), daemon=True)
                t.start()
            except Exception:
                break

    def _handle_client(self, local_sock):
        try:
            peek_data = local_sock.recv(4096, socket.MSG_PEEK)
            if not peek_data:
                local_sock.close()
                return

            # Check if SOCKS5 protocol
            if peek_data[0] == 0x05:
                self._handle_socks5(local_sock)
            else:
                # Handle HTTP / HTTPS CONNECT
                self._handle_http_connect(local_sock)
        except Exception:
            try:
                local_sock.close()
            except Exception:
                pass

    def _handle_http_connect(self, local_sock):
        try:
            req_line = b""
            while b"\r\n" not in req_line:
                chunk = local_sock.recv(1)
                if not chunk:
                    return
                req_line += chunk

            parts = req_line.decode("utf-8", errors="ignore").strip().split(" ")
            if len(parts) < 2:
                return

            method, target = parts[0], parts[1]

            # Discard remaining HTTP request headers until double CRLF
            header_buf = b""
            while b"\r\n\r\n" not in header_buf:
                chunk = local_sock.recv(1)
                if not chunk:
                    break
                header_buf += chunk

            if method.upper() == "CONNECT":
                # HTTPS Tunneling
                if ":" in target:
                    host, port_str = target.split(":", 1)
                    port = int(port_str)
                else:
                    host = target
                    port = 443

                # Connect to remote XION server
                remote_sock = socket.create_connection((self.remote_server_host, self.remote_server_port), timeout=8)
                enc_sock = EncryptedSocket(remote_sock, self.aes_key)

                # Send destination request
                req_payload = json.dumps({"host": host, "port": port}).encode("utf-8")
                enc_sock.send_packet(req_payload)

                resp_payload = enc_sock.recv_packet()
                resp = json.loads(resp_payload.decode("utf-8")) if resp_payload else {}
                if resp.get("status") != "ok":
                    local_sock.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                    enc_sock.close()
                    return

                # Send 200 Connection Established to local client
                local_sock.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                self._pipe_data(local_sock, enc_sock)

            else:
                # Standard HTTP GET/POST proxying
                from urllib.parse import urlparse
                parsed = urlparse(target)
                host = parsed.hostname or target.split("/")[0]
                port = parsed.port or 80

                remote_sock = socket.create_connection((self.remote_server_host, self.remote_server_port), timeout=8)
                enc_sock = EncryptedSocket(remote_sock, self.aes_key)

                req_payload = json.dumps({"host": host, "port": port}).encode("utf-8")
                enc_sock.send_packet(req_payload)

                resp_payload = enc_sock.recv_packet()
                resp = json.loads(resp_payload.decode("utf-8")) if resp_payload else {}
                if resp.get("status") != "ok":
                    local_sock.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                    enc_sock.close()
                    return

                # Reconstruct first request line and send
                path = parsed.path if parsed.path else "/"
                if parsed.query:
                    path += "?" + parsed.query
                first_line = f"{method} {path} HTTP/1.1\r\n".encode("utf-8")
                enc_sock.send_packet(first_line + header_buf)

                self._pipe_data(local_sock, enc_sock)

        except Exception:
            pass
        finally:
            try:
                local_sock.close()
            except Exception:
                pass

    def _handle_socks5(self, local_sock):
        try:
            # SOCKS5 greeting
            ver, nmethods = local_sock.recv(2)
            methods = local_sock.recv(nmethods)
            local_sock.sendall(b"\x05\x00")  # No auth required

            # Connection request
            ver, cmd, rsv, atyp = local_sock.recv(4)
            if cmd != 0x01:  # Only CONNECT supported
                return

            if atyp == 0x01:  # IPv4
                dest_ip_bytes = local_sock.recv(4)
                host = socket.inet_ntoa(dest_ip_bytes)
            elif atyp == 0x03:  # Domain name
                domain_len = local_sock.recv(1)[0]
                host = local_sock.recv(domain_len).decode("utf-8")
            else:
                return

            port_bytes = local_sock.recv(2)
            port = int.from_bytes(port_bytes, "big")

            # Connect to remote XION server
            remote_sock = socket.create_connection((self.remote_server_host, self.remote_server_port), timeout=8)
            enc_sock = EncryptedSocket(remote_sock, self.aes_key)

            req_payload = json.dumps({"host": host, "port": port}).encode("utf-8")
            enc_sock.send_packet(req_payload)

            resp_payload = enc_sock.recv_packet()
            resp = json.loads(resp_payload.decode("utf-8")) if resp_payload else {}
            if resp.get("status") != "ok":
                local_sock.sendall(b"\x05\x05\x00\x01\x00\x00\x00\x00\x00\x00")
                enc_sock.close()
                return

            # Reply success to client
            local_sock.sendall(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
            self._pipe_data(local_sock, enc_sock)

        except Exception:
            pass
        finally:
            try:
                local_sock.close()
            except Exception:
                pass

    def _pipe_data(self, local_sock, enc_sock):
        def local_to_enc():
            try:
                while True:
                    data = local_sock.recv(16384)
                    if not data:
                        break
                    enc_sock.send_packet(data)
            except Exception:
                pass
            finally:
                enc_sock.close()

        def enc_to_local():
            try:
                while True:
                    data = enc_sock.recv_packet()
                    if not data:
                        break
                    local_sock.sendall(data)
            except Exception:
                pass
            finally:
                try:
                    local_sock.close()
                except Exception:
                    pass

        t1 = threading.Thread(target=local_to_enc, daemon=True)
        t2 = threading.Thread(target=enc_to_local, daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

    def stop(self):
        self.running = False
        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass
