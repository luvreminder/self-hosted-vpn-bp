#!/usr/bin/env python3
"""
Subscription Gateway & Node Transformer (Sub-Enhancer)
Hardened reverse proxy for 3X-UI subscription endpoints:
- Injects descriptive node titles from the hosts table (Cellular / Wi-Fi / CDN).
- Normalizes URL typos, trailing slashes, and redundant delimiters.
- Adds client refresh intervals (Profile-Update-Interval: 12) and strict security headers.
- Normalizes spiderX percent-encoding and Reality Vision TCP parameters.
- Configures SOTA XHTTP URL-encoded JSON `extra` (xPaddingBytes + xmux) parameters.
- Normalizes both Xray [...] and Sing-box {...} JSON subscriptions & Direct-IP endpoints.
- Supports non-blocking worker-thread Dual HTTP/HTTPS (MSG_PEEK 0x16) on shared ports.
"""

import sys
import os
import re
import ssl
import json
import socket
import sqlite3
import base64
import ipaddress
import threading
import urllib.error
import urllib.request
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

UPSTREAM = os.environ.get("SUB_UPSTREAM", "http://127.0.0.1:2095")
DB_PATH = os.environ.get("XUI_DB_PATH", "/etc/x-ui/x-ui.db")
SUB_LISTEN = os.environ.get("SUB_LISTEN", "0.0.0.0")
SSL_CERT = os.environ.get("SUB_SSL_CERT", "/etc/x-ui/sub_cert.pem")
SSL_KEY = os.environ.get("SUB_SSL_KEY", "/etc/x-ui/sub_key.pem")
SUB_PUBLIC_IP = os.environ.get("SUB_PUBLIC_IP", "").strip()

DEFAULT_XHTTP_EXTRA_OBJ = {
    "xPaddingBytes": "100-1000",
    "xmux": {
        "maxConcurrency": "16-32",
        "cMaxReuseTimes": "64-128",
        "hMaxRequestTimes": "600-800",
        "hMaxReusableSecs": "1800-2400",
        "hKeepAlivePeriod": 30,
    },
}
DEFAULT_XHTTP_EXTRA = urllib.parse.quote(
    json.dumps(DEFAULT_XHTTP_EXTRA_OBJ, separators=(",", ":")), safe=""
)

STRIPPED_RESPONSE_HEADERS = frozenset({
    "content-length",
    "transfer-encoding",
    "connection",
    "profile-update-interval",
    "server",
    "x-powered-by",
    "cache-control",
    "x-content-type-options",
})


def get_host_mappings():
    """Retrieve mapping dictionaries from 3X-UI SQLite database."""
    if not os.path.exists(DB_PATH):
        return {}, {}
    try:
        conn = sqlite3.connect(DB_PATH, timeout=2.0)
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT remark, server_description, sni FROM hosts "
            "WHERE is_disabled=0 AND remark IS NOT NULL AND remark != ''"
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


def format_uri_host(host):
    """Format host for URI authority (bracketing bare IPv6 literals)."""
    bare = host.strip().strip("[]")
    if ":" in bare:
        return f"[{bare}]"
    return bare


def _is_ip_or_local(host):
    """Return True if host is localhost or a literal IPv4/IPv6 address."""
    bare = host.strip().strip("[]")
    if bare.lower() in ("localhost", ""):
        return True
    try:
        ipaddress.ip_address(bare)
        return True
    except ValueError:
        return False


def _clean_query_delimiters(url):
    """Ensure clean single '?' before query parameters and no duplicate '&'."""
    if "?" in url:
        base, query = url.split("?", 1)
        query = query.replace("?", "&")
    elif "&" in url:
        base, query = url.split("&", 1)
    else:
        return url
    parts = [p for p in query.split("&") if p]
    return f"{base}?{'&'.join(parts)}" if parts else base


def rewrite_vless_endpoint(main_part, public_host, connect_ip=""):
    """Rewrite localhost endpoints and apply SOTA Direct-IP SNI preservation."""
    if public_host:
        uri_pub = format_uri_host(public_host)
        main_part = re.sub(
            r"@(?:localhost|127\.0\.0\.1|\[::1\]):",
            f"@{uri_pub}:",
            main_part,
        )

    if not connect_ip:
        return main_part

    match = re.search(r"@(\[[0-9a-fA-F:]+\]|[^/?#:]+):(\d+)", main_part)
    if not match:
        return main_part

    orig_host, port = match.group(1), match.group(2)
    uri_ip = format_uri_host(connect_ip)
    main_part = main_part[:match.start()] + f"@{uri_ip}:{port}" + main_part[match.end():]

    if not _is_ip_or_local(orig_host):
        encoded_orig = urllib.parse.quote(orig_host, safe="")
        if "sni=" not in main_part:
            main_part += f"&sni={encoded_orig}"
        is_http_transport = any(t in main_part for t in ("type=xhttp", "type=ws", "type=httpupgrade"))
        if is_http_transport and "host=" not in main_part:
            main_part += f"&host={encoded_orig}"

    return _clean_query_delimiters(main_part)


def _is_xhttp_node(main_part):
    """Return True if VLESS URI uses XHTTP transport."""
    return "type=xhttp" in main_part or "net=xhttp" in main_part


def _merge_xhttp_extra(main_part):
    """Ensure XHTTP extra JSON contains xPaddingBytes and xmux ranges (merging 3X-UI mode stubs)."""
    match = re.search(r"([?&])extra=([^&]*)", main_part)
    if not match:
        return main_part + f"&extra={DEFAULT_XHTTP_EXTRA}"

    raw_val = urllib.parse.unquote(match.group(2))
    try:
        parsed = json.loads(raw_val) if raw_val else {}
    except ValueError:
        return main_part

    if not isinstance(parsed, dict):
        return main_part

    merged = dict(parsed)
    changed = False
    for key in ("xPaddingBytes", "xmux"):
        if key not in merged:
            merged[key] = DEFAULT_XHTTP_EXTRA_OBJ[key]
            changed = True

    if not changed:
        return main_part

    encoded = urllib.parse.quote(json.dumps(merged, separators=(",", ":")), safe="")
    return f"{main_part[:match.start()]}{match.group(1)}extra={encoded}{main_part[match.end():]}"


def normalize_reality_node(main_part):
    """Apply strict hardening for Reality nodes (XHTTP SOTA and legacy TCP Vision)."""
    main_part = re.sub(r"[?&]support-x25519mlkem768=[^&]*", "", main_part)
    main_part = re.sub(r"[?&]spx=[^&]*", "&spx=%2F", main_part)

    if _is_xhttp_node(main_part):
        main_part = re.sub(r"[?&](?:flow|xmux|maxConcurrency)=[^&]*", "", main_part)
        if "mode=" not in main_part:
            main_part += "&mode=auto"
        if "path=" not in main_part:
            main_part += "&path=%2Fapi%2Fv2%2Fsync"
        main_part = _merge_xhttp_extra(main_part)
    else:
        main_part = re.sub(r"[?&]type=[^&]+", "&type=tcp", main_part)
        main_part = re.sub(r"[?&](?:xmux|maxConcurrency|mode|extra)=[^&]*", "", main_part)
        if "flow=" in main_part:
            main_part = re.sub(r"flow=[^&]+", "flow=xtls-rprx-vision", main_part)
        else:
            main_part += "&flow=xtls-rprx-vision"

    if "fp=" not in main_part:
        main_part += "&fp=chrome"

    return _clean_query_delimiters(main_part)


def normalize_tls_node(main_part):
    """Normalize Direct TLS / XHTTP nodes."""
    if _is_xhttp_node(main_part):
        main_part = re.sub(r"[?&](?:flow|xmux|maxConcurrency)=[^&]*", "", main_part)
        if "mode=" not in main_part:
            main_part += "&mode=auto"
        main_part = _merge_xhttp_extra(main_part)

    if "fp=" not in main_part:
        main_part += "&fp=chrome"

    return _clean_query_delimiters(main_part)


def _resolve_connect_ip(connect_ip):
    """Resolve optional SUB_CONNECT_IP override when not explicitly passed."""
    if connect_ip is None:
        return os.environ.get("SUB_CONNECT_IP", "").strip()
    return connect_ip.strip()


def process_vless_line(line, sub_host, desc_map, sni_map, connect_ip=None):
    """Process and normalize a single VLESS line."""
    if not line.startswith("vless://"):
        return line

    effective_connect = _resolve_connect_ip(connect_ip)
    main_part, _, fragment = line.partition("#")
    main_part = rewrite_vless_endpoint(main_part, sub_host, effective_connect)

    if "security=reality" in main_part:
        main_part = normalize_reality_node(main_part)
    elif "security=tls" in main_part:
        main_part = normalize_tls_node(main_part)
    else:
        main_part = _clean_query_delimiters(main_part)

    parsed = urllib.parse.urlsplit(main_part)
    query = urllib.parse.parse_qs(parsed.query)
    sni = query.get("sni", [""])[0].strip()

    title = resolve_node_title(fragment, sni, desc_map, sni_map)
    return f"{main_part}#{urllib.parse.quote(title)}"


def transform_base64_payload(body, sub_host, desc_map, sni_map, connect_ip=None):
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
        cleaned = process_vless_line(line, sub_host, desc_map, sni_map, connect_ip=connect_ip)
        main_url = cleaned.partition("#")[0]
        if main_url not in seen:
            seen.add(main_url)
            new_lines.append(cleaned)

    return base64.b64encode("\n".join(new_lines).encode("utf-8"))


def _rewrite_json_host_field(obj, key, bare_public, bare_connect):
    """Rewrite a single JSON host key ('address' or 'server') in-place."""
    val = obj.get(key)
    if not isinstance(val, str):
        return
    if val.strip().lower() in ("localhost", "127.0.0.1", "::1", "[::1]") and bare_public:
        obj[key] = bare_public
    elif bare_connect and not _is_ip_or_local(val):
        obj[key] = bare_connect


def _rewrite_json_node(obj, bare_public, bare_connect):
    """Recursively normalize server endpoints across Xray and Sing-box JSON objects."""
    if isinstance(obj, list):
        for item in obj:
            _rewrite_json_node(item, bare_public, bare_connect)
        return
    if not isinstance(obj, dict):
        return

    if "server" in obj and ("type" in obj or "server_port" in obj):
        _rewrite_json_host_field(obj, "server", bare_public, bare_connect)
    if "address" in obj and ("port" in obj or "users" in obj):
        _rewrite_json_host_field(obj, "address", bare_public, bare_connect)

    for key, val in obj.items():
        if key not in ("dns", "inbounds"):
            _rewrite_json_node(val, bare_public, bare_connect)


def transform_json_payload(body, sub_host, connect_ip=None):
    """Normalize addresses in Xray [...] and Sing-box {...} JSON subscription payloads."""
    effective_connect = _resolve_connect_ip(connect_ip)
    bare_public = (effective_connect or sub_host or "").strip().strip("[]")
    bare_connect = effective_connect.strip("[]")
    if not bare_public and not bare_connect:
        return body

    try:
        raw_text = body.decode("utf-8", errors="ignore").strip()
        if not raw_text or raw_text[0] not in ("[", "{"):
            return body
        data = json.loads(raw_text)
        _rewrite_json_node(data, bare_public, bare_connect)
        return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    except Exception as err:
        sys.stderr.write(f"JSON normalize error: {err}\n")
        return body


def _sanitize_header_value(value):
    """Sanitize header values to Latin-1 without CR/LF/NEL injection."""
    safe_v = str(value).replace("\r", " ").replace("\n", " ").replace("\x85", " ")
    try:
        safe_v.encode("latin-1")
        return safe_v
    except UnicodeEncodeError:
        return safe_v.encode("utf-8", errors="ignore").decode("latin-1", errors="replace")


class SubHandler(BaseHTTPRequestHandler):
    """Hardened reverse proxy HTTP handler for 3X-UI subscription endpoints."""

    def log_message(self, format, *args):
        return

    def send_response(self, code, message=None):
        self.send_response_only(code, message)
        self.send_header("Date", self.date_time_string())

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

    def _send_security_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, private")
        self.send_header("X-Content-Type-Options", "nosniff")

    def _forward_filtered_headers(self, headers):
        for k, v in headers.items():
            if k.lower() in STRIPPED_RESPONSE_HEADERS:
                continue
            self.send_header(k, _sanitize_header_value(v))

    def send_error_response(self, code, msg, method="GET"):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self._send_security_headers()
        raw_msg = msg.encode("utf-8")
        self.send_header("Content-Length", str(len(raw_msg)))
        self.end_headers()
        if method != "HEAD" and raw_msg:
            self.wfile.write(raw_msg)

    def send_upstream_error(self, err, method="GET"):
        try:
            self.send_response(err.code)
            self._forward_filtered_headers(err.headers)
            self._send_security_headers()
            err_body = err.read() if method != "HEAD" else b""
        finally:
            err.close()
        self.send_header("Content-Length", str(len(err_body)))
        self.end_headers()
        if method != "HEAD" and err_body:
            self.wfile.write(err_body)

    def send_transformed_response(self, status, headers, body, method):
        self.send_response(status)
        self._forward_filtered_headers(headers)
        self.send_header("Profile-Update-Interval", "12")
        self._send_security_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if method == "GET" and body:
            self.wfile.write(body)

    def handle_proxy(self, method):
        try:
            status, headers, body = self.forward_upstream(method)
        except urllib.error.HTTPError as err:
            self.send_upstream_error(err, method=method)
            return
        except Exception as err:
            self.send_error_response(502, f"Bad Gateway (Upstream 3X-UI unreachable): {err}", method=method)
            return

        if status == 200 and method == "GET" and body:
            connect_ip = os.environ.get("SUB_CONNECT_IP", "").strip()
            sub_host = (
                connect_ip
                or os.environ.get("SUB_PUBLIC_IP", "").strip()
                or SUB_PUBLIC_IP
                or os.environ.get("SUB_DOMAIN", "").strip()
            )
            desc_map, sni_map = get_host_mappings()
            stripped_body = body.lstrip()
            if stripped_body.startswith((b"[", b"{")):
                body = transform_json_payload(body, sub_host, connect_ip=connect_ip)
            else:
                body = transform_base64_payload(body, sub_host, desc_map, sni_map, connect_ip=connect_ip)

        self.send_transformed_response(status, headers, body, method)


def _negotiate_dual_socket(sock, ssl_ctx, client_addr):
    """Peek first byte in worker thread to upgrade TLS connections without blocking accept."""
    if not ssl_ctx:
        sock.settimeout(15.0)
        return sock
    try:
        sock.settimeout(3.0)
        first_byte = sock.recv(1, socket.MSG_PEEK)
        sock.settimeout(15.0)
        if first_byte == b"\x16":
            return ssl_ctx.wrap_socket(sock, server_side=True)
    except Exception as err:
        sys.stderr.write(f"TLS wrap notice for {client_addr[0]}: {err} (serving as plain HTTP)\n")
        try:
            sock.settimeout(15.0)
        except OSError as timeout_err:
            sys.stderr.write(f"Socket settimeout notice: {timeout_err}\n")
    return sock


class DualProtocolServer(ThreadingHTTPServer):
    """
    Dual-protocol HTTP and HTTPS server supporting simultaneous plain HTTP and TLS
    on the same port via non-blocking worker-thread MSG_PEEK 0x16 protocol sniffing.
    """

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass, ssl_ctx=None):
        self.ssl_ctx = ssl_ctx
        max_conn = int(os.environ.get("SUB_MAX_CONCURRENCY", "128"))
        self._conn_sem = threading.BoundedSemaphore(max(1, max_conn))
        super().__init__(server_address, RequestHandlerClass)

    def get_request(self):
        sock, addr = self.socket.accept()
        sock.settimeout(15.0)
        return sock, addr

    def process_request(self, request, client_address):
        if not self._conn_sem.acquire(blocking=False):
            sys.stderr.write(f"Concurrency limit reached; dropping {client_address[0]}\n")
            self.shutdown_request(request)
            return
        thread = threading.Thread(
            target=self.process_request_thread,
            args=(request, client_address),
        )
        thread.daemon = self.daemon_threads
        thread.start()

    def process_request_thread(self, request, client_address):
        try:
            negotiated = _negotiate_dual_socket(request, self.ssl_ctx, client_address)
            super().process_request_thread(negotiated, client_address)
        except Exception as err:
            sys.stderr.write(f"Worker connection error for {client_address[0]}: {err}\n")
            self.shutdown_request(request)
        finally:
            self._conn_sem.release()


def resolve_listen_ports():
    """Determine gateway listener ports, avoiding port 80 collision in Single-Port-443 mode."""
    single_port = os.environ.get("SUB_SINGLE_PORT_443", "").strip().lower() in ("true", "1", "yes")
    raw_env = os.environ.get("SUB_PORTS", "2096,28443,80").strip()
    if single_port and raw_env == "2096,28443,80":
        return [2096]
    ports = [int(item.strip()) for item in raw_env.split(",") if item.strip().isdigit()]
    return ports or [2096]


def load_ssl_context():
    """Load optional server TLS context when certificates exist and TLS is not disabled."""
    force_no_tls = os.environ.get("SUB_ENABLE_TLS", "").strip().lower() in ("false", "0", "no")
    if force_no_tls or not (os.path.exists(SSL_CERT) and os.path.exists(SSL_KEY)):
        return None
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile=SSL_CERT, keyfile=SSL_KEY)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        print(f"[+] TLS certificates loaded successfully from {SSL_CERT} (Dual HTTP/HTTPS active)")
        return ctx
    except Exception as err:
        print(f"[!] Warning: Failed to load TLS certificates ({err}). Starting in plain HTTP mode.")
        return None


def start_server(listen_ip, port, ssl_ctx=None):
    server = DualProtocolServer((listen_ip, port), SubHandler, ssl_ctx)
    proto = "Dual (HTTP/HTTPS)" if ssl_ctx else "HTTP (Plain)"
    print(f"[*] Sub-Enhancer listening on {listen_ip}:{port} ({proto})")
    server.serve_forever()


def run_gateway_servers(listen_ip, ports, ssl_ctx=None):
    """Bind all requested listener ports resiliently and serve concurrently."""
    servers = []
    for port in ports:
        try:
            srv = DualProtocolServer((listen_ip, port), SubHandler, ssl_ctx)
            proto = "Dual (HTTP/HTTPS)" if ssl_ctx else "HTTP (Plain)"
            print(f"[*] Sub-Enhancer listening on {listen_ip}:{port} ({proto})")
            servers.append(srv)
        except OSError as err:
            sys.stderr.write(f"[!] Warning: Could not bind {listen_ip}:{port}: {err}\n")

    if not servers:
        sys.stderr.write("[!] Fatal: Failed to bind any subscription gateway port.\n")
        sys.exit(1)

    for srv in servers[:-1]:
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
    servers[-1].serve_forever()


if __name__ == "__main__":
    run_gateway_servers(SUB_LISTEN, resolve_listen_ports(), load_ssl_context())
