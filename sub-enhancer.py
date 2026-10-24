#!/usr/bin/env python3
"""
Subscription Gateway & Node Transformer (Sub-Enhancer)
Hardened reverse proxy for 3X-UI subscription endpoints:
- Injects descriptive node titles from the hosts table (Cellular / Wi-Fi / CDN).
- Normalizes URL typos, trailing slashes, and redundant delimiters.
- Adds client refresh intervals (Profile-Update-Interval: 12).
- Normalizes spiderX percent-encoding for client compatibility.
- Adds high-availability Direct TLS and XHTTP nodes.
"""

import sys
import os
import re
import ssl
import socket
import sqlite3
import base64
import urllib.request
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

UPSTREAM = os.environ.get("SUB_UPSTREAM", "http://127.0.0.1:2095")
DB_PATH = os.environ.get("XUI_DB_PATH", "/etc/x-ui/x-ui.db")
SUB_LISTEN = os.environ.get("SUB_LISTEN", "0.0.0.0")
SSL_CERT = os.environ.get("SUB_SSL_CERT", "/etc/x-ui/sub_cert.pem")
SSL_KEY = os.environ.get("SUB_SSL_KEY", "/etc/x-ui/sub_key.pem")
SUB_PUBLIC_IP = os.environ.get("SUB_PUBLIC_IP", "").strip()

def get_host_mappings():
    """Retrieve mapping dictionaries from 3X-UI SQLite database."""
    if not os.path.exists(DB_PATH):
        return {}, {}
    try:
        conn = sqlite3.connect(DB_PATH, timeout=2.0)
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT remark, server_description, sni FROM hosts WHERE is_disabled=0 AND remark IS NOT NULL AND remark != ''"
        ).fetchall()
        conn.close()
        desc_map = {}
        sni_map = {}
        for remark, desc, sni in rows:
            if desc and desc.strip():
                desc_map[desc.strip()] = remark.strip()
            if sni and sni.strip() and sni.strip() not in sni_map:
                sni_map[sni.strip()] = remark.strip()
        return desc_map, sni_map
    except Exception:
        return {}, {}

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

        if status == 200 and method == "GET" and body:
            try:
                raw_text = body.decode("utf-8", errors="ignore")
                if raw_text.strip().startswith("[") and ("outbounds" in raw_text or "settings" in raw_text):
                    sub_host = os.environ.get("SUB_CONNECT_IP", "").strip() or SUB_PUBLIC_IP or os.environ.get("SUB_DOMAIN", "").strip()
                    if sub_host:
                        raw_text = re.sub(r'("address"\s*:\s*)"(?:localhost|127\.0\.0\.1)"', rf'\1"{sub_host}"', raw_text)
                        body = raw_text.encode("utf-8")
            except Exception:
                pass

            try:
                padded_body = body.strip()
                padding_needed = (-len(padded_body)) % 4
                if padding_needed:
                    padded_body += b"=" * padding_needed

                decoded = base64.b64decode(padded_body).decode("utf-8", errors="ignore")
                if "vless://" in decoded:
                    desc_map, sni_map = get_host_mappings()
                    # Prefer direct IP for connection endpoint to eliminate DDNS lookup failures / ISP DNS throttling
                    sub_host = os.environ.get("SUB_CONNECT_IP", "").strip() or SUB_PUBLIC_IP or os.environ.get("SUB_DOMAIN", "").strip()
                    raw_lines = decoded.strip().splitlines()
                    new_lines = []
                    seen_urls = set()
                    for line in raw_lines:
                        line = line.strip()
                        if line.startswith("vless://"):
                            if sub_host:
                                line = re.sub(r"@(localhost|127\.0\.0\.1):", f"@{sub_host}:", line)
                            line = re.sub(r"([?&]spx=)/", r"\g<1>%2F", line)
                            main_part, _, fragment = line.partition("#")
                            parsed = urllib.parse.urlsplit(main_part)
                            query = urllib.parse.parse_qs(parsed.query)
                            sni = query.get("sni", [""])[0].strip()

                            title = None
                            frag_match = re.search(r"serverDescription=([A-Za-z0-9+/=]+)", fragment)
                            if frag_match:
                                try:
                                    decoded_desc = base64.b64decode(frag_match.group(1)).decode("utf-8").strip()
                                    if decoded_desc in desc_map:
                                        title = desc_map[decoded_desc]
                                except Exception:
                                    pass

                            if not title:
                                unquoted_frag = urllib.parse.unquote(fragment).strip()
                                if unquoted_frag and "serverDescription=" not in unquoted_frag:
                                    title = unquoted_frag.split("|")[0].split("?")[0].strip()

                            if not title:
                                title = sni_map.get(sni)
                            if not title:
                                title = f"Node ({sni})" if sni else "Gateway Node"

                            if ("security=tls" in main_part or "security=reality" in main_part) and "fp=" not in main_part:
                                sep = "&" if "?" in main_part else "?"
                                main_part += f"{sep}fp=chrome"

                            # Next-Gen SOTA: XHTTP XMUX session rotation
                            if "type=xhttp" in main_part or "net=xhttp" in main_part:
                                if "mode=" not in main_part:
                                    sep = "&" if "?" in main_part else "?"
                                    main_part += f"{sep}mode=auto"
                                if "xmux=" not in main_part:
                                    sep = "&" if "?" in main_part else "?"
                                    main_part += f"{sep}xmux=1&maxConcurrency=16"

                            # Next-Gen SOTA: Optional TLS Hello Fragmentation for Direct TLS evasion
                            if "security=tls" in main_part and "security=reality" not in main_part:
                                enable_frag = os.environ.get("SUB_ENABLE_FRAGMENT", "false").strip().lower() in ("true", "1", "yes")
                                frag_val = os.environ.get("SUB_FRAGMENT_VAL", "100-200%2C1-3%2Ctlshello").strip()
                                if enable_frag and "fragment=" not in main_part:
                                    sep = "&" if "?" in main_part else "?"
                                    main_part += f"{sep}fragment={frag_val}"

                            # Next-Gen SOTA: Single Port 443 multiplexing port normalization
                            single_port_443 = os.environ.get("SUB_SINGLE_PORT_443", "false").strip().lower() in ("true", "1", "yes")
                            if single_port_443:
                                main_part = re.sub(r":(?:8443|2083)\?", ":443?", main_part)

                            clean_node = f"{main_part}#{urllib.parse.quote(title)}"
                            if main_part not in seen_urls:
                                seen_urls.add(main_part)
                                new_lines.append(clean_node)
                        elif line and line not in seen_urls:
                            seen_urls.add(line)
                            new_lines.append(line)

                    body = base64.b64encode("\n".join(new_lines).encode("utf-8"))
            except Exception:
                pass

        self.send_response(status)
        for k, v in headers.items():
            if k.lower() not in ("content-length", "transfer-encoding", "connection", "profile-update-interval"):
                self.send_header(k, v)

        self.send_header("Profile-Update-Interval", "12")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, private")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()

        if method == "GET" and body:
            self.wfile.write(body)

class DualProtocolServer(ThreadingHTTPServer):
    """
    Dual-protocol HTTP and HTTPS server supporting simultaneous plain HTTP and TLS
    on the exact same listener port via Layer-7 protocol sniffing (MSG_PEEK 0x16).
    """
    def __init__(self, server_address, RequestHandlerClass, ssl_ctx=None):
        self.ssl_ctx = ssl_ctx
        super().__init__(server_address, RequestHandlerClass)

    def get_request(self):
        sock, addr = self.socket.accept()
        if self.ssl_ctx:
            try:
                first_byte = sock.recv(1, socket.MSG_PEEK)
                if first_byte == b"\x16":
                    sock = self.ssl_ctx.wrap_socket(sock, server_side=True)
            except Exception:
                try:
                    sock.close()
                except Exception:
                    pass
                raise
        return sock, addr

def start_server(listen_ip, port, ssl_ctx=None):
    server = DualProtocolServer((listen_ip, port), SubHandler, ssl_ctx)
    proto = "Dual (HTTP/HTTPS)" if ssl_ctx else "HTTP (Plain)"
    print(f"[*] Sub-Enhancer listening on {listen_ip}:{port} ({proto})")
    server.serve_forever()

if __name__ == "__main__":
    import threading

    ssl_context = None
    force_no_tls = os.environ.get("SUB_ENABLE_TLS", "").strip().lower() in ("false", "0", "no")
    if not force_no_tls and os.path.exists(SSL_CERT) and os.path.exists(SSL_KEY):
        try:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(certfile=SSL_CERT, keyfile=SSL_KEY)
            ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
            print(f"[+] TLS certificates loaded successfully from {SSL_CERT} (Dual HTTP/HTTPS active)")
        except Exception as e:
            print(f"[!] Warning: Failed to load TLS certificates ({e}). Starting in plain HTTP mode.")
            ssl_context = None

    raw_ports = os.environ.get("SUB_PORTS", "2096,28443").split(",")
    ports = [int(p.strip()) for p in raw_ports if p.strip()]

    for p in ports[:-1]:
        t = threading.Thread(target=start_server, args=(SUB_LISTEN, p, ssl_context), daemon=True)
        t.start()

    start_server(SUB_LISTEN, ports[-1], ssl_context)
