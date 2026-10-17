#!/usr/bin/env python3
"""
Subscription Gateway & Node Transformer (Sub-Enhancer)
Hardened reverse proxy for 3X-UI subscription endpoints:
- Injects descriptive node titles from the hosts table (Cellular / Wi-Fi / CDN).
- Normalizes URL typos, trailing slashes, and redundant delimiters.
- Adds client refresh intervals (Profile-Update-Interval: 12).
- Supports optional TLS/HTTPS encryption to prevent ISP DPI from sniffing VLESS credentials.
"""

import sys
import os
import re
import ssl
import sqlite3
import base64
import urllib.request
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

UPSTREAM = os.environ.get("SUB_UPSTREAM", "http://127.0.0.1:2095")
DB_PATH = os.environ.get("XUI_DB_PATH", "/etc/x-ui/x-ui.db")
SUB_LISTEN = os.environ.get("SUB_LISTEN", "127.0.0.1")
SSL_CERT = os.environ.get("SUB_SSL_CERT", "/etc/x-ui/sub_cert.pem")
SSL_KEY = os.environ.get("SUB_SSL_KEY", "/etc/x-ui/sub_key.pem")
SUB_PUBLIC_IP = os.environ.get("SUB_PUBLIC_IP", "").strip()

def get_sni_remarks():
    """Retrieve SNI to Remark mapping from 3X-UI SQLite database."""
    if not os.path.exists(DB_PATH):
        return {}
    try:
        conn = sqlite3.connect(DB_PATH, timeout=2.0)
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT sni, remark FROM hosts WHERE is_disabled=0 AND remark IS NOT NULL AND remark != ''"
        ).fetchall()
        conn.close()
        return {sni.strip(): remark.strip() for sni, remark in rows if sni and sni.strip()}
    except Exception:
        return {}

def normalize_request_path(raw_path):
    """Normalize client URL typos, redundant slashes, and whitespace."""
    parsed = urllib.parse.urlsplit(raw_path)
    clean_path = re.sub(r"/+", "/", parsed.path).strip()
    if not clean_path.startswith("/"):
        clean_path = "/" + clean_path
    if parsed.query:
        return f"{clean_path}?{parsed.query}"
    return clean_path

class SubHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress noisy standard access logging; uncomment for debugging
        pass

    def do_GET(self):
        self.proxy_request("GET")

    def do_HEAD(self):
        self.proxy_request("HEAD")

    def proxy_request(self, method):
        normalized_path = normalize_request_path(self.path)
        upstream_url = UPSTREAM + normalized_path

        req_headers = {
            k: v for k, v in self.headers.items()
            if k.lower() not in ("host", "content-length", "connection")
        }
        req = urllib.request.Request(upstream_url, headers=req_headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                status = resp.status
                headers = dict(resp.headers)
                body = resp.read() if method == "GET" else b""
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            for k, v in e.headers.items():
                if k.lower() not in ("content-length", "transfer-encoding", "connection"):
                    self.send_header(k, v)
            body = e.read()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if method == "GET":
                self.wfile.write(body)
            return
        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            msg = f"Bad Gateway (Upstream 3X-UI unreachable): {e}".encode("utf-8")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            if method == "GET":
                self.wfile.write(msg)
            return

        # Transform subscription content
        if status == 200 and method == "GET" and body:
            try:
                # Add base64 padding if needed
                padded_body = body.strip()
                padding_needed = (-len(padded_body)) % 4
                if padding_needed:
                    padded_body += b"=" * padding_needed

                decoded = base64.b64decode(padded_body).decode("utf-8", errors="ignore")
                if "vless://" in decoded:
                    sni_map = get_sni_remarks()
                    lines = decoded.strip().splitlines()
                    new_lines = []
                    for line in lines:
                        line = line.strip()
                        if line.startswith("vless://"):
                            # Auto-heal missing host address from 3X-UI localhost fallback if SUB_PUBLIC_IP is configured
                            if SUB_PUBLIC_IP:
                                line = re.sub(r"@(localhost|127\.0\.0\.1):", f"@{SUB_PUBLIC_IP}:", line)
                            main_part, _, _ = line.partition("#")
                            parsed = urllib.parse.urlsplit(main_part)
                            query = urllib.parse.parse_qs(parsed.query)
                            sni = query.get("sni", [""])[0].strip()
                            title = sni_map.get(sni)
                            if not title:
                                title = f"Node ({sni})" if sni else "Golden Standard Proxy"
                            new_lines.append(f"{main_part}#{urllib.parse.quote(title)}")
                        elif line:
                            new_lines.append(line)
                    body = base64.b64encode("\n".join(new_lines).encode("utf-8"))
            except Exception:
                pass

        self.send_response(status)
        for k, v in headers.items():
            if k.lower() not in ("content-length", "transfer-encoding", "connection", "profile-update-interval"):
                self.send_header(k, v)

        # Standard subscription control and anti-caching headers
        self.send_header("Profile-Update-Interval", "12")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, private")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()

        if method == "GET" and body:
            self.wfile.write(body)

def start_server(listen_ip, port, ssl_ctx=None):
    server = ThreadingHTTPServer((listen_ip, port), SubHandler)
    if ssl_ctx:
        server.socket = ssl_ctx.wrap_socket(server.socket, server_side=True)
        proto = "HTTPS (TLS)"
    else:
        proto = "HTTP (Plain)"
    print(f"[*] Sub-Enhancer listening on {listen_ip}:{port} ({proto})")
    server.serve_forever()

if __name__ == "__main__":
    import threading

    ssl_context = None
    if os.path.exists(SSL_CERT) and os.path.exists(SSL_KEY):
        try:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(certfile=SSL_CERT, keyfile=SSL_KEY)
            # Modern TLS recommendations
            ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
            print(f"[+] TLS certificates loaded successfully from {SSL_CERT}")
        except Exception as e:
            print(f"[!] Warning: Failed to load TLS certificates ({e}). Starting in plain HTTP mode.")
            ssl_context = None

    raw_ports = os.environ.get("SUB_PORTS", "2096,28443").split(",")
    ports = [int(p.strip()) for p in raw_ports if p.strip()]

    for p in ports[:-1]:
        t = threading.Thread(target=start_server, args=(SUB_LISTEN, p, ssl_context), daemon=True)
        t.start()

    start_server(SUB_LISTEN, ports[-1], ssl_context)
