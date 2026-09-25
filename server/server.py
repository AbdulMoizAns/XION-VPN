"""
server.py - XION VPN Standalone Encrypted Server
Run this script on any remote Linux VPS or PC:
  python server.py --port 8080 --password my_secret_key
"""
import argparse
import json
import socket
import threading
from crypto_tunnel import derive_aes_key, EncryptedSocket

def handle_tunnel_connection(client_sock, client_addr, aes_key):
    enc_sock = EncryptedSocket(client_sock, aes_key)
    target_sock = None
    try:
        # Step 1: Read target destination request from client
        raw_req = enc_sock.recv_packet()
        if not raw_req:
            return
        
        try:
            req = json.loads(raw_req.decode("utf-8"))
            host = req.get("host")
            port = req.get("port")
        except Exception:
            enc_sock.send_packet(json.dumps({"status": "error", "message": "Invalid request payload"}).encode("utf-8"))
            return

        if not host or not port:
            enc_sock.send_packet(json.dumps({"status": "error", "message": "Missing host or port"}).encode("utf-8"))
            return

        # Step 2: Connect to the requested internet host
        try:
            target_sock = socket.create_connection((host, int(port)), timeout=10)
            enc_sock.send_packet(json.dumps({"status": "ok"}).encode("utf-8"))
        except Exception as e:
            enc_sock.send_packet(json.dumps({"status": "error", "message": str(e)}).encode("utf-8"))
            return

        # Step 3: Bi-directional relay between encrypted tunnel and target host
        def client_to_target():
            try:
                while True:
                    data = enc_sock.recv_packet()
                    if not data:
                        break
                    target_sock.sendall(data)
            except Exception:
                pass
            finally:
                try:
                    target_sock.shutdown(socket.SHUT_WR)
                except Exception:
                    pass

        def target_to_client():
            try:
                while True:
                    data = target_sock.recv(16384)
                    if not data:
                        break
                    enc_sock.send_packet(data)
            except Exception:
                pass
            finally:
                enc_sock.close()

        t1 = threading.Thread(target=client_to_target, daemon=True)
        t2 = threading.Thread(target=target_to_client, daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

    except Exception as e:
        print(f"[-] Error handling connection from {client_addr}: {e}")
    finally:
        enc_sock.close()
        if target_sock:
            try:
                target_sock.close()
            except Exception:
                pass

def start_server(host: str, port: int, password: str):
    aes_key = derive_aes_key(password)
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((host, port))
    server_sock.listen(128)

    print("=" * 60)
    print(f"  XION VPN Server running on {host}:{port}")
    print(f"  Security: AES-256-GCM Authenticated Encryption")
    print("=" * 60)
    print("[*] Waiting for encrypted connections...")

    try:
        while True:
            client_sock, client_addr = server_sock.accept()
            t = threading.Thread(target=handle_tunnel_connection, args=(client_sock, client_addr, aes_key), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("\n[*] Shutting down server...")
    finally:
        server_sock.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="XION VPN Remote Server")
    parser.add_argument("--host", default="0.0.0.0", help="Binding host (default 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="Binding port (default 8080)")
    parser.add_argument("--password", default="xion_secret_pass_2026", help="Shared secret password")
    args = parser.parse_args()

    start_server(args.host, args.port, args.password)
