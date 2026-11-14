#!/usr/bin/env python3
"""Automated SOTA & Next-Gen SOTA verification suite for community-edition."""

import ast
import base64
import importlib.util
import json
import os
import pathlib
import re
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import threading
import time
import types
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _DummySSLCtx:
    """Minimal SSL context stub activating MSG_PEEK without X.509 cert files."""

    def wrap_socket(self, sock, server_side=True):
        raise AssertionError("Unexpected TLS handshake on plain HTTP test traffic")


class TestWarpWireGuard(unittest.TestCase):
    """Validate RFC 7748 Curve25519 crypto, reserved bytes, and template updates."""

    @classmethod
    def setUpClass(cls):
        cls.gw = _load_module("generate_warp_wireguard", ROOT / "generate_warp_wireguard.py")

    def test_rfc7748_section6_x25519_vector(self):
        scalar_bytes = bytearray.fromhex(
            "a546e36bf0527c9d3b16154b82465edd62144c0ac1fc5a18506a2244ba449ac4"
        )
        scalar_bytes[0] &= 248
        scalar_bytes[31] &= 127
        scalar_bytes[31] |= 64

        u_bytes = bytearray.fromhex(
            "e6db6867583030db3594c1a424b15f7c726624ec26b3353b10a903a6d0ab1c4c"
        )
        u_bytes[31] &= 127

        res_int = self.gw._mult(
            int.from_bytes(scalar_bytes, "little"),
            int.from_bytes(u_bytes, "little"),
        )
        expected = "c3da55379de9c6908e94ea4df28d084f32eccf03491c71f754b4075577a28552"
        self.assertEqual(res_int.to_bytes(32, "little").hex(), expected)

    def test_decode_reserved_bytes(self):
        valid_b64 = base64.b64encode(bytes([12, 34, 56])).decode("ascii")
        self.assertEqual(self.gw.decode_reserved_bytes(valid_b64), [12, 34, 56])
        self.assertEqual(self.gw.decode_reserved_bytes("not-b64!!"), [0, 0, 0])
        too_long = base64.b64encode(b"1234").decode("ascii")
        self.assertEqual(self.gw.decode_reserved_bytes(too_long), [0, 0, 0])

    def test_apply_outbound_to_template_preserves_sockopt_and_removes_socks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tpl_copy = pathlib.Path(tmpdir) / "xray_template.json"
            shutil.copy(ROOT / "xray_template_config.json", tpl_copy)

            outbound = self.gw.build_xray_outbound(
                "TEST_PRIV_KEY_B64=",
                {
                    "config": {
                        "interface": {"addresses": {"v4": "172.16.0.2", "v6": "2606:4700::2"}},
                        "client_id": base64.b64encode(bytes([1, 2, 3])).decode("ascii"),
                        "peers": [{"public_key": "PEER_PUB=", "endpoint": {"host": "162.159.192.1:2408"}}],
                    }
                },
            )
            self.gw.apply_outbound_to_template(str(tpl_copy), outbound)

            updated = json.loads(tpl_copy.read_text(encoding="utf-8"))
            tags = [o["tag"] for o in updated["outbounds"]]
            self.assertIn("warp-wireguard", tags)
            self.assertNotIn("warp-socks", tags)

            direct = next(o for o in updated["outbounds"] if o["tag"] == "direct")
            self.assertEqual(direct["streamSettings"]["sockopt"]["tcpKeepAliveIdle"], 20)

            rules = updated["routing"]["rules"]
            udp443_blocks = [
                r for r in rules
                if r.get("outboundTag") == "blocked" and r.get("network") == "udp"
            ]
            self.assertEqual(udp443_blocks, [])
            ai_routes = [r for r in rules if r.get("outboundTag") == "warp-wireguard"]
            self.assertEqual(len(ai_routes), 1)


class TestSubEnhancer(unittest.TestCase):
    """Validate SOTA XHTTP extra=, Direct-IP, JSON payloads, and non-blocking concurrency."""

    @classmethod
    def setUpClass(cls):
        cls.se = _load_module("sub_enhancer", ROOT / "sub-enhancer.py")

    def test_xhttp_reality_injects_encoded_extra_and_strips_flow(self):
        raw = (
            "vless://11111111-1111-1111-1111-111111111111@localhost:443"
            "?type=xhttp&security=reality&flow=xtls-rprx-vision&xmux=1&maxConcurrency=16"
            "&support-x25519mlkem768=1&sni=example.com#Node"
        )
        out = self.se.process_vless_line(raw, "203.0.113.10", {}, {}, connect_ip="")
        main_part, _, _ = out.partition("#")
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(main_part).query)

        self.assertIn("@203.0.113.10:443", main_part)
        self.assertNotIn("flow", query)
        self.assertNotIn("xmux", query)
        self.assertNotIn("maxConcurrency", query)
        self.assertNotIn("support-x25519mlkem768", query)
        self.assertEqual(query["mode"], ["auto"])
        self.assertEqual(query["path"], ["/api/v2/sync"])
        self.assertEqual(query["fp"], ["chrome"])

        extra_obj = json.loads(query["extra"][0])
        self.assertIn("xPaddingBytes", extra_obj)
        self.assertIn("xmux", extra_obj)

    def test_xhttp_preserves_custom_extra(self):
        custom = urllib.parse.quote('{"xPaddingBytes":"50-200"}', safe="")
        raw = (
            f"vless://11111111-1111-1111-1111-111111111111@example.com:443"
            f"?type=xhttp&security=tls&mode=packet-up&extra={custom}#Custom"
        )
        out = self.se.normalize_tls_node(raw.partition("#")[0])
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(out).query)
        extra_custom = json.loads(query["extra"][0])
        self.assertEqual(extra_custom["xPaddingBytes"], "50-200")
        self.assertIn("xmux", extra_custom)

        # Simulate 3X-UI 3.10.2 mode-only stub extra={"mode":"auto"}
        stub = urllib.parse.quote('{"mode":"auto"}', safe="")
        stub_raw = (
            f"vless://11111111-1111-1111-1111-111111111111@localhost:443"
            f"?extra={stub}&sni=example.org&type=xhttp&security=reality#Stub"
        )
        stub_out = self.se.process_vless_line(stub_raw, "203.0.113.10", {}, {}, connect_ip="")
        stub_extra = json.loads(
            urllib.parse.parse_qs(urllib.parse.urlsplit(stub_out.partition("#")[0]).query)["extra"][0]
        )
        self.assertEqual(stub_extra["mode"], "auto")
        self.assertEqual(stub_extra["xPaddingBytes"], "100-1000")
        self.assertIn("xmux", stub_extra)

    def test_tcp_reality_enforces_vision_and_spx(self):
        raw = (
            "vless://11111111-1111-1111-1111-111111111111@203.0.113.10:443"
            "?type=tcp&security=reality&spx=/test&support-x25519mlkem768=true&sni=dl.google.com#TCP"
        )
        out = self.se.process_vless_line(raw, "", {}, {}, connect_ip="")
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(out.partition("#")[0]).query)
        self.assertEqual(query["flow"], ["xtls-rprx-vision"])
        self.assertEqual(query["spx"], ["/"])
        self.assertIn("spx=%2F", out)

    def test_direct_ip_rewriting_and_ipv6_brackets(self):
        raw = "vless://uuid-1@vpn.example.org:443?type=xhttp&security=tls#Direct"
        out = self.se.process_vless_line(
            raw, "2001:db8::1", {}, {}, connect_ip="2001:db8::1"
        )
        main_part = out.partition("#")[0]
        self.assertIn("@[2001:db8::1]:443", main_part)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(main_part).query)
        self.assertEqual(query["sni"], ["vpn.example.org"])
        self.assertEqual(query["host"], ["vpn.example.org"])

    def test_transform_json_payload_xray_and_singbox(self):
        xray_cfg = [
            {
                "inbounds": [{"listen": "127.0.0.1", "port": 10808, "protocol": "socks"}],
                "outbounds": [
                    {
                        "protocol": "vless",
                        "settings": {"vnext": [{"address": "localhost", "port": 443, "users": []}]},
                    }
                ],
                "dns": {"servers": ["localhost"]},
            }
        ]
        res_xray = json.loads(
            self.se.transform_json_payload(
                json.dumps(xray_cfg).encode("utf-8"), "198.51.100.5", connect_ip=""
            ).decode("utf-8")
        )
        self.assertEqual(res_xray[0]["outbounds"][0]["settings"]["vnext"][0]["address"], "198.51.100.5")
        self.assertEqual(res_xray[0]["inbounds"][0]["listen"], "127.0.0.1")
        self.assertEqual(res_xray[0]["dns"]["servers"], ["localhost"])

        singbox_cfg = {
            "dns": {"servers": [{"type": "udp", "server": "1.1.1.1"}]},
            "outbounds": [
                {"type": "vless", "tag": "proxy", "server": "vpn.example.org", "server_port": 443}
            ],
        }
        res_sb = json.loads(
            self.se.transform_json_payload(
                json.dumps(singbox_cfg).encode("utf-8"), "198.51.100.5", connect_ip="198.51.100.5"
            ).decode("utf-8")
        )
        self.assertEqual(res_sb["outbounds"][0]["server"], "198.51.100.5")
        self.assertEqual(res_sb["dns"]["servers"][0]["server"], "1.1.1.1")

    def test_live_dual_protocol_server_non_blocking_and_error_headers(self):
        sub_line = "vless://11111111-1111-1111-1111-111111111111@localhost:443?type=xhttp&security=reality&sni=dl.google.com#Demo"
        b64_payload = base64.b64encode(sub_line.encode("utf-8"))

        class _MockUpstream(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                return

            def do_GET(self):
                if self.path == "/sub/valid":
                    self.send_response(200)
                    self.send_header("Server", "x-ui")
                    self.send_header("Content-Length", str(len(b64_payload)))
                    self.end_headers()
                    self.wfile.write(b64_payload)
                    return
                self.send_response(404)
                self.send_header("Server", "x-ui")
                self.send_header("Content-Length", "9")
                self.end_headers()
                self.wfile.write(b"Not Found")

        upstream = HTTPServer(("127.0.0.1", 0), _MockUpstream)
        up_port = upstream.server_address[1]
        up_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        up_thread.start()

        old_upstream = self.se.UPSTREAM
        old_public = self.se.SUB_PUBLIC_IP
        self.se.UPSTREAM = f"http://127.0.0.1:{up_port}"
        self.se.SUB_PUBLIC_IP = "203.0.113.77"
        gateway = self.se.DualProtocolServer(("127.0.0.1", 0), self.se.SubHandler, ssl_ctx=_DummySSLCtx())
        gw_port = gateway.server_address[1]
        gw_thread = threading.Thread(target=gateway.serve_forever, daemon=True)
        gw_thread.start()

        idle_sock = None
        try:
            idle_sock = socket.create_connection(("127.0.0.1", gw_port), timeout=5.0)
            t0 = time.monotonic()
            with urllib.request.urlopen(f"http://127.0.0.1:{gw_port}/sub//valid", timeout=2.0) as resp:
                elapsed = time.monotonic() - t0
                self.assertEqual(resp.status, 200)
                self.assertLess(elapsed, 1.0)
                self.assertEqual(resp.headers.get("Profile-Update-Interval"), "12")
                self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")
                self.assertIsNone(resp.headers.get("Server"))
                decoded = base64.b64decode(resp.read()).decode("utf-8")
                self.assertIn("@203.0.113.77:443", decoded)
                self.assertIn("extra=", decoded)

            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(f"http://127.0.0.1:{gw_port}/", timeout=2.0)
            self.assertEqual(ctx.exception.code, 404)
            self.assertEqual(ctx.exception.headers.get("X-Content-Type-Options"), "nosniff")
            self.assertIn("no-store", ctx.exception.headers.get("Cache-Control", ""))
            self.assertIsNone(ctx.exception.headers.get("Server"))
            ctx.exception.close()
        finally:
            if idle_sock is not None:
                idle_sock.close()
            gateway.shutdown()
            gateway.server_close()
            upstream.shutdown()
            upstream.server_close()
            self.se.UPSTREAM = old_upstream
            self.se.SUB_PUBLIC_IP = old_public


class TestMonthlyMaintenance(unittest.TestCase):
    """Validate section-aware credential parsing, ShortId hygiene, and Native WARP preservation."""

    @classmethod
    def setUpClass(cls):
        cls.mm = _load_module("run_monthly_maintenance", ROOT / "run_monthly_maintenance.py")

    def test_resolve_credentials_is_section_aware(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            key_file = pathlib.Path(tmpdir) / "id_test_ed25519"
            key_file.write_text("dummy", encoding="utf-8")
            cred_file = pathlib.Path(tmpdir) / "credentials.txt"
            cred_file.write_text(
                "\n".join([
                    "[SERVER]",
                    "IP = 198.51.100.42",
                    "SSH_PORT = 2222",
                    "SSH_USER = opsadmin",
                    f"SSH_KEY_PATH = {key_file}",
                    "",
                    "[PANEL_3X_UI]",
                    "LOCAL_PORT = 23600",
                    "USERNAME = paneladmin",
                    "PASSWORD = PanelOnlySecretShouldNotLeakToSSH",
                    "",
                    "[VLESS_REALITY]",
                    "REALITY_PRIVATE_KEY = FakeRealityPrivKey",
                ]),
                encoding="utf-8",
            )
            parsed = self.mm._parse_credentials_file(str(cred_file))
            self.assertEqual(parsed["host"], "198.51.100.42")
            self.assertEqual(parsed["port"], 2222)
            self.assertEqual(parsed["user"], "opsadmin")
            self.assertEqual(parsed["key_path"], str(key_file))
            self.assertIsNone(parsed["password"])

            args = types.SimpleNamespace(host=None, port=None, user=None, password=None, key=None)
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                host, port, user, password, key_path = self.mm.resolve_credentials(args)
            finally:
                os.chdir(old_cwd)
            self.assertEqual((host, port, user, password, key_path), ("198.51.100.42", 2222, "opsadmin", None, str(key_file)))

    def test_remote_script_ast_shortids_and_preserves_native_wireguard(self):
        ast.parse(self.mm.REMOTE_SCRIPT)
        self.assertNotIn('existing_sids.add("859a72d4fa0c9a5e")', self.mm.REMOTE_SCRIPT)

        module_ast = ast.parse(self.mm.REMOTE_SCRIPT)
        selected = [
            node for node in module_ast.body
            if isinstance(node, ast.FunctionDef)
            and node.name in ("_detect_native_wireguard_outbound", "build_xray_template_config")
        ]
        ns = {"json": json, "os": os}
        exec(compile(ast.Module(body=selected, type_ignores=[]), "<remote>", "exec"), ns)

        existing = {
            "outbounds": [
                {
                    "tag": "warp-wireguard",
                    "protocol": "wireguard",
                    "settings": {"secretKey": "REAL_PRIVATE_WG_KEY="},
                }
            ]
        }
        rebuilt, tag, _ = ns["build_xray_template_config"](existing, wg_file="/nonexistent")
        self.assertEqual(tag, "warp-wireguard")
        out_tags = [o["tag"] for o in rebuilt["outbounds"]]
        self.assertIn("warp-wireguard", out_tags)
        self.assertNotIn("warp-socks", out_tags)

        direct = next(o for o in rebuilt["outbounds"] if o["tag"] == "direct")
        self.assertEqual(direct["streamSettings"]["sockopt"]["tcpKeepAliveIdle"], 20)


class TestDeployAndClientTools(unittest.TestCase):
    """Validate universal_deploy.sh parity, client-tools hardening, and line endings."""

    def test_universal_deploy_invariants_and_sub_enhancer_sync(self):
        ud = (ROOT / "universal_deploy.sh").read_text(encoding="utf-8")
        self.assertIn("libnginx-mod-stream", ud)
        self.assertIn("/etc/sysctl.d/99-sota-vpn.conf", ud)
        self.assertIn("net.ipv4.tcp_mtu_probing=1", ud)
        self.assertIn("net.ipv4.tcp_fastopen=3", ud)
        self.assertIn("ip6tables", ud)
        self.assertIn('Environment="SUB_PUBLIC_IP=${SUB_PUBLIC_IP_VAL:-}"', ud)
        self.assertIn("vps-maintenance.timer", ud)
        self.assertNotIn('--update-template "$TEMPLATE_FILE"', ud)
        self.assertLess(ud.index("TEMPLATE_FILE="), ud.index("WARP_GEN_SCRIPT="))

        match = re.search(
            r'cat << \'EOF\' > "\$TARGET_ENHANCER"\n(.*?)\nEOF\nfi', ud, re.S
        )
        self.assertIsNotNone(match)
        embedded = match.group(1) + "\n"
        ast.parse(embedded)
        self.assertIn("import socket", embedded)
        standalone = (ROOT / "sub-enhancer.py").read_text(encoding="utf-8")
        self.assertEqual(embedded, standalone)

    def test_line_endings_and_bash_syntax(self):
        for rel in (
            "generate_warp_wireguard.py",
            "sub-enhancer.py",
            "run_monthly_maintenance.py",
            "xray_template_config.json",
            "universal_deploy.sh",
            "README.md",
            "client-tools/change_password.sh",
            "client-tools/open_panel_localhost.sh",
        ):
            self.assertNotIn(b"\r\n", (ROOT / rel).read_bytes(), f"Unexpected CRLF in {rel}")

        for rel in (
            "client-tools/change_password.bat",
            "client-tools/open_panel_localhost.bat",
        ):
            raw = (ROOT / rel).read_bytes()
            self.assertIn(b"\r\n", raw, f"Expected CRLF in {rel}")

        git_bash = pathlib.Path(r"C:\Program Files\Git\bin\bash.exe")
        if git_bash.exists():
            for sh_rel in (
                "universal_deploy.sh",
                "client-tools/change_password.sh",
                "client-tools/open_panel_localhost.sh",
            ):
                proc = subprocess.run(
                    [str(git_bash), "-n", str(ROOT / sh_rel)],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()

