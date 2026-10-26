#!/usr/bin/env python3
"""
Subscription Gateway & Node Transformer (Sub-Enhancer)
Hardened reverse proxy for 3X-UI subscription endpoints:
- Injects descriptive node titles from the hosts table (Cellular / Wi-Fi / CDN).
- Normalizes URL typos, trailing slashes, and redundant delimiters.
- Adds client refresh intervals (Profile-Update-Interval: 12).
- Normalizes spiderX percent-encoding for client compatibility.
- Normalizes Reality Vision TCP parameters (removes ML-KEM fragmentation).
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
    except Exception as err:
        sys.stderr.write(f"DB mapping error: {err}\n")
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


def parse_desc_match(fragment, desc_map):
    """Attempt decoding base64 serverDescription from URL fragment."""
    frag_match = re.search(r"serverDescription=([A-Za-z0-9+/=]+)", fragment)
    if not frag_match:
        return ""
    try:
        decoded = base64.b64decode(frag_match.group(1)).decode("utf-8").strip()
        return desc_map.get(decoded, "")
    except Exception as err:
        sys.stderr.write(f"Desc match error: {err}\n")
        return ""


def resolve_node_title(fragment, sni, desc_map, sni_map):
    """Resolve descriptive remark title for a VLESS node."""
    title = parse_desc_match(fragment, desc_map)
    if title:
        return title

    unquoted_frag = urllib.parse.unquote(fragment).strip()
    if unquoted_frag and "serverDescription=" not in unquoted_frag:
        return unquoted_frag.split("|")[0].split("?")[0].strip()

    if sni and sni in sni_map:
        return sni_map[sni]

    return f"Node ({sni})" if sni else "Gateway Node"


def normalize_reality_node(main_part):
    """Apply strict hardening for Reality nodes (supporting both XHTTP SOTA and legacy TCP Vision)."""
    main_part = re.sub(r"[?&]support-x25519mlkem768=[^&]+", "", main_part)
    main_part = re.sub(r"[?&]spx=[^&]*", "&spx=%2F", main_part)

    # Check if this is an XHTTP Reality node
    if "type=xhttp" in main_part or "net=xhttp" in main_part:
        # XHTTP Reality: no flow, requires mode=auto and path
        main_part = re.sub(r"[?&]flow=[^&]+", "", main_part)
        if "mode=" not in main_part:
            main_part += "&mode=auto"
        if "path=" not in main_part:
            main_part += "&path=%2Fapi%2Fv2%2Fsync"
        if "xmux=" not in main_part:
            main_part += "&xmux=1&maxConcurrency=16"
    else:
        # Classic TCP Reality: requires flow=xtls-rprx-vision
        main_part = re.sub(r"[?&]type=[^&]+", "&type=tcp", main_part)
        main_part = re.sub(r"[?&](?:xmux|maxConcurrency|mode)=[^&]+", "", main_part)
        if "flow=" in main_part:
            main_part = re.sub(r"flow=[^&]+", "flow=xtls-rprx-vision", main_part)
        else:
            main_part += "&flow=xtls-rprx-vision"

    if "fp=" not in main_part:
        main_part += "&fp=chrome"

    return main_part


def normalize_tls_node(main_part):
    """Normalize Direct TLS / XHTTP nodes."""
    if "type=xhttp" in main_part or "net=xhttp" in main_part:
        if "mode=" not in main_part:
            main_part += "&mode=auto"
        if "xmux=" not in main_part:
            main_part += "&xmux=1&maxConcurrency=16"

    if "fp=" not in main_part:
        main_part += "&fp=chrome"

    return main_part


def process_vless_line(line, sub_host, desc_map, sni_map):
    """Process and normalize a single VLESS line."""
    if not line.startswith("vless://"):
        return line

    if sub_host:
        line = re.sub(r"@(localhost|127\.0\.0\.1):", f"@{sub_host}:", line)

    main_part, _, fragment = line.partition("#")
    parsed = urllib.parse.urlsplit(main_part)
    query = urllib.parse.parse_qs(parsed.query)
    sni = query.get("sni", [""])[0].strip()

    if "security=reality" in main_part:
        main_part = normalize_reality_node(main_part)
    elif "security=tls" in main_part:
        main_part = normalize_tls_node(main_part)

    if "?" not in main_part and "&" in main_part:
        main_part = main_part.replace("&", "?", 1)

    title = resolve_node_title(fragment, sni, desc_map, sni_map)
    return f"{main_part}#{urllib.parse.quote(title)}"


def transform_base64_payload(body, sub_host, desc_map, sni_map):
    """Decode, process and re-encode base64 subscription payload."""
    padded = body.strip()
    padding_needed = (-len(padded)) % 4
    if padding_needed:
        padded += b"=" * padding_needed

    try:
        decoded = base64.b64decode(padded).decode("utf-8", errors="ignore")
    except Exception as err:
        sys.stderr.write(f"B64 decode error: {err}\n")
        return body

    if "vless://" not in decoded:
        return body

    seen = set()
    new_lines = []
    for line in decoded.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        cleaned = process_vless_line(line, sub_host, desc_map, sni_map)
        main_url = cleaned.partition("#")[0]
        if main_url not in seen:
            seen.add(main_url)
            new_lines.append(cleaned)

    return base64.b64encode("\n".join(new_lines).encode("utf-8"))


def transform_json_payload(body, sub_host):
    """Normalize addresses in JSON payload for client imports."""
    if not sub_host:
        return body
    try:
        raw_text = body.decode("utf-8", errors="ignore")
        if raw_text.strip().startswith("[") and ("outbounds" in raw_text or "settings" in raw_text):
            raw_text = re.sub(r'("address"\s*:\s*)"(?:localhost|127\.0\.0\.1)"', rf'\1"{sub_host}"', raw_text)
            return raw_text.encode("utf-8")
    except Exception as err:
        sys.stderr.write(f"JSON normalize error: {err}\n")
    return body


class SubHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        self.handle_proxy("GET")

    def do_HEAD(self):
        self.handle_proxy("HEAD")

    def forward_upstream(self, method):
        normalized_path = normalize_request_path(self.path)
        upstream_url = UPSTREAM + normalized_path
        req_headers = {
            k: v for k, v in self.headers.items()
            if k.lower() not in ("host", "content-length", "connection")
        }
        req = urllib.request.Request(upstream_url, headers=req_headers, method=method)
        with urllib.request.urlopen(req, timeout=8.0) as resp:
            body = resp.read() if method == "GET" else b""
            return resp.status, dict(resp.headers), body

    def send_error_response(self, code, msg):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        raw_msg = msg.encode("utf-8")
        self.send_header("Content-Length", str(len(raw_msg)))
        self.end_headers()
        self.wfile.write(raw_msg)

    def send_upstream_error(self, err):
        self.send_response(err.code)
        for k, v in err.headers.items():
            if k.lower() not in ("content-length", "transfer-encoding", "connection"):
                self.send_header(k, v)
        err_body = err.read()
        self.send_header("Content-Length", str(len(err_body)))
        self.end_headers()
        self.wfile.write(err_body)

    def send_transformed_response(self, status, headers, body, method):
        self.send_response(status)
        for k, v in headers.items():
            if k.lower() in ("content-length", "transfer-encoding", "connection", "profile-update-interval"):
                continue
            # Sanitize header value to safe ASCII/Latin-1 to prevent HTTP response splitting / NEL 0x85 corruption
            safe_v = str(v).replace("\r", " ").replace("\n", " ").replace("\x85", " ")
            try:
                safe_v.encode("latin-1")
            except UnicodeEncodeError:
                safe_v = safe_v.encode("utf-8", errors="ignore").decode("latin-1", errors="replace")
            self.send_header(k, safe_v)
        self.send_header("Profile-Update-Interval", "12")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, private")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if method == "GET" and body:
            self.wfile.write(body)

    def handle_proxy(self, method):
        try:
            status, headers, body = self.forward_upstream(method)
        except urllib.error.HTTPError as err:
            self.send_upstream_error(err)
            return
        except Exception as err:
            self.send_error_response(502, f"Bad Gateway (Upstream 3X-UI unreachable): {err}")
            return

        if status == 200 and method == "GET" and body:
            sub_host = os.environ.get("SUB_CONNECT_IP", "").strip() or SUB_PUBLIC_IP or os.environ.get("SUB_DOMAIN", "").strip()
            desc_map, sni_map = get_host_mappings()
            stripped_body = body.strip()
            if stripped_body.startswith(b"[") or stripped_body.startswith(b"{"):
                body = transform_json_payload(body, sub_host)
            else:
                body = transform_base64_payload(body, sub_host, desc_map, sni_map)

        self.send_transformed_response(status, headers, body, method)


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
        if not self.ssl_ctx:
            sock.settimeout(15.0)
            return sock, addr

        try:
            sock.settimeout(5.0)
            first_byte = sock.recv(1, socket.MSG_PEEK)
            sock.settimeout(15.0)
            if first_byte == b"\x16":
                sock = self.ssl_ctx.wrap_socket(sock, server_side=True)
        except Exception as err:
            sys.stderr.write(f"TLS wrap notice for {addr[0]}: {err} (serving as plain HTTP)\n")
            try:
                sock.settimeout(15.0)
            except OSError as timeout_err:
                sys.stderr.write(f"Socket settimeout notice: {timeout_err}\n")

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
        except Exception as err:
            print(f"[!] Warning: Failed to load TLS certificates ({err}). Starting in plain HTTP mode.")
            ssl_context = None

    raw_ports = os.environ.get("SUB_PORTS", "2096,28443,80").split(",")
    ports = [int(p.strip()) for p in raw_ports if p.strip()]

    for p in ports[:-1]:
        t = threading.Thread(target=start_server, args=(SUB_LISTEN, p, ssl_context), daemon=True)
        t.start()

    start_server(SUB_LISTEN, ports[-1], ssl_context)
