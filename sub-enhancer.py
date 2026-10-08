#!/usr/bin/env python3
import sys
import os
import sqlite3
import base64
import urllib.request
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

# Gateway Settings
UPSTREAM = "http://127.0.0.1:2095"
DB_PATH = "/etc/x-ui/x-ui.db"

def get_sni_remarks():
    try:
        conn = sqlite3.connect(DB_PATH, timeout=2.0)
        cur = conn.cursor()
        rows = cur.execute("SELECT sni, remark FROM hosts WHERE is_disabled=0 AND remark IS NOT NULL AND remark != ''").fetchall()
        conn.close()
        return {sni: remark for sni, remark in rows if sni}
    except Exception:
        return {}

class SubHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        self.proxy_request("GET")

    def do_HEAD(self):
        self.proxy_request("HEAD")

    def proxy_request(self, method):
        upstream_url = UPSTREAM + self.path
        req_headers = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "content-length")}
        req = urllib.request.Request(upstream_url, headers=req_headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
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
            msg = f"Bad Gateway: {e}".encode()
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            if method == "GET":
                self.wfile.write(msg)
            return

        # Normalize subscription node names
        if status == 200 and method == "GET" and body:
            try:
                decoded = base64.b64decode(body).decode("utf-8", errors="ignore")
                if "vless://" in decoded:
                    sni_map = get_sni_remarks()
                    lines = decoded.strip().splitlines()
                    new_lines = []
                    for line in lines:
                        if line.startswith("vless://"):
                            main_part, _, _ = line.partition("#")
                            parsed = urllib.parse.urlparse(main_part)
                            query = urllib.parse.parse_qs(parsed.query)
                            sni = query.get("sni", [""])[0]
                            title = sni_map.get(sni, "Proxy Node")
                            new_lines.append(f"{main_part}#{urllib.parse.quote(title)}")
                        else:
                            new_lines.append(line)
                    body = base64.b64encode("\n".join(new_lines).encode("utf-8"))
            except Exception:
                pass

        self.send_response(status)
        for k, v in headers.items():
            if k.lower() not in ("content-length", "transfer-encoding", "connection", "profile-update-interval"):
                self.send_header(k, v)
        self.send_header("Profile-Update-Interval", "12")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if method == "GET" and body:
            self.wfile.write(body)

def start_server(port):
    server = ThreadingHTTPServer(("0.0.0.0", port), SubHandler)
    server.serve_forever()

if __name__ == "__main__":
    import threading
    ports = [int(p.strip()) for p in os.environ.get("SUB_PORTS", "2096,28443").split(",") if p.strip()]
    for p in ports[:-1]:
        t = threading.Thread(target=start_server, args=(p,), daemon=True)
        t.start()
    start_server(ports[-1])
