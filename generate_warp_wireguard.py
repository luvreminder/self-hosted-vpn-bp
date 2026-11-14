#!/usr/bin/env python3
"""
Native Cloudflare WARP WireGuard Account Generator & Outbound Builder
Generates zero-overhead WireGuard configurations directly for Xray Core.
Eliminates warp-svc daemon dependencies, saves ~100MB RAM, and supports UDP/QUIC.
"""

import sys
import os
import json
import base64
import urllib.request
import urllib.error
import datetime
import argparse

# Curve25519 pure Python Montgomery ladder implementation (zero external dependencies)
P = 2**255 - 19

def _mult(d, p):
    x1 = p
    x2, z2 = 1, 0
    x3, z3 = p, 1
    for i in reversed(range(255)):
        b = 1 & (d >> i)
        x2, x3 = (x3, x2) if b else (x2, x3)
        z2, z3 = (z3, z2) if b else (z2, z3)
        a = (x2 + z2) % P
        aa = (a * a) % P
        b_ = (x2 - z2) % P
        bb = (b_ * b_) % P
        e = (aa - bb) % P
        c = (x3 + z3) % P
        d_ = (x3 - z3) % P
        da = (d_ * a) % P
        cb = (c * b_) % P
        x3 = ((da + cb)**2) % P
        z3 = (x1 * (da - cb)**2) % P
        x2 = (aa * bb) % P
        z2 = (e * (aa + 121665 * e)) % P
        x2, x3 = (x3, x2) if b else (x2, x3)
        z2, z3 = (z3, z2) if b else (z2, z3)
    return (x2 * pow(z2, P - 2, P)) % P

def generate_keypair():
    """Generates standard Curve25519 private/public keypair in base64 format."""
    priv = bytearray(os.urandom(32))
    priv[0] &= 248
    priv[31] &= 127
    priv[31] |= 64
    priv_int = int.from_bytes(priv, "little")
    pub_int = _mult(priv_int, 9)
    pub = pub_int.to_bytes(32, "little")
    priv_b64 = base64.b64encode(priv).decode("ascii")
    pub_b64 = base64.b64encode(pub).decode("ascii")
    return priv_b64, pub_b64

def register_warp(pub_b64):
    """Registers client public key with Cloudflare WARP client API."""
    url = "https://api.cloudflareclient.com/v0a2158/reg"
    payload = {
        "key": pub_b64,
        "install_id": "",
        "fcm_token": "",
        "tos": datetime.datetime.now(datetime.timezone.utc).isoformat()[:-9] + "Z",
        "model": "PC",
        "serial_number": "",
        "locale": "en_US"
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "User-Agent": "okhttp/3.12.1",
            "Content-Type": "application/json; charset=UTF-8"
        },
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=15) as resp:
        if resp.status not in (200, 201):
            raise RuntimeError(f"Cloudflare registration HTTP {resp.status}")
        return json.loads(resp.read().decode("utf-8"))

def decode_reserved_bytes(client_id_raw: str) -> list[int]:
    """Decode base64 Cloudflare client_id into a 3-byte WireGuard reserved field."""
    if not client_id_raw:
        return [0, 0, 0]
    try:
        raw_bytes = base64.b64decode(client_id_raw, validate=True)
    except Exception as err:
        sys.stderr.write(f"[!] Invalid WARP client_id encoding ({err}); defaulting reserved to [0, 0, 0]\n")
        return [0, 0, 0]
    if len(raw_bytes) != 3:
        sys.stderr.write(f"[!] Unexpected client_id byte length ({len(raw_bytes)}); defaulting reserved to [0, 0, 0]\n")
        return [0, 0, 0]
    return list(raw_bytes)


def extract_peer_config(peers: list) -> tuple[str, str]:
    """Extract Cloudflare WARP peer public key and endpoint from API response."""
    default_pub = "bmXOC+F1FxEMF9dyiK2H5/1SUtzH0JuVo51h2wPfgyo="
    default_endpoint = "engage.cloudflareclient.com:2408"
    if not peers or not isinstance(peers[0], dict):
        return default_pub, default_endpoint

    peer = peers[0]
    peer_pub = peer.get("public_key") or default_pub
    endpoint_obj = peer.get("endpoint", {})
    if isinstance(endpoint_obj, dict):
        peer_endpoint = endpoint_obj.get("host") or default_endpoint
    elif isinstance(endpoint_obj, str) and endpoint_obj.strip():
        peer_endpoint = endpoint_obj.strip()
    else:
        peer_endpoint = default_endpoint
    return peer_pub, peer_endpoint


def _extract_interface_addresses(config: dict) -> list[str]:
    """Extract IPv4/IPv6 CIDR addresses from WARP interface config."""
    iface = config.get("interface", {}).get("addresses", {})
    v4_addr = iface.get("v4") or "192.0.2.2"
    if "/" not in v4_addr:
        v4_addr = f"{v4_addr}/32"

    addresses = [v4_addr]
    v6_addr = iface.get("v6", "")
    if v6_addr:
        if "/" not in v6_addr:
            v6_addr = f"{v6_addr}/128"
        addresses.append(v6_addr)
    return addresses


def build_xray_outbound(priv_b64, reg_response):
    """Constructs Xray Core native WireGuard outbound configuration object."""
    config = reg_response.get("result", {}).get("config", {})
    if not config:
        config = reg_response.get("config", {})

    addresses = _extract_interface_addresses(config)
    reserved = decode_reserved_bytes(config.get("client_id", ""))
    peer_pub, peer_endpoint = extract_peer_config(config.get("peers", []))

    return {
        "tag": "warp-wireguard",
        "protocol": "wireguard",
        "settings": {
            "secretKey": priv_b64,
            "address": addresses,
            "peers": [
                {
                    "publicKey": peer_pub,
                    "endpoint": peer_endpoint,
                    "reserved": reserved
                }
            ],
            "kernelMode": False,
            "mtu": 1280
        }
    }


def write_secure_json(path: str, payload: dict) -> None:
    """Write JSON configuration with LF endings and strict 0600 permissions."""
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    try:
        os.chmod(path, 0o600)
    except OSError as err:
        sys.stderr.write(f"[!] Note: Could not apply chmod 0600 to {path}: {err}\n")


def _is_ai_quic_block_rule(rule: dict) -> bool:
    """Return True if routing rule is the legacy UDP/443 AI QUIC block."""
    return (
        rule.get("outboundTag") == "blocked"
        and rule.get("network") == "udp"
        and str(rule.get("port", "")) == "443"
    )


def apply_outbound_to_template(template_path: str, outbound: dict) -> None:
    """Update an Xray template JSON file with the native WireGuard outbound."""
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template file {template_path} not found")

    with open(template_path, "r", encoding="utf-8") as f:
        template = json.load(f)

    new_outbounds = []
    inserted = False
    for out in template.get("outbounds", []):
        tag = out.get("tag")
        if tag == "warp-socks":
            continue
        if tag == "warp-wireguard":
            new_outbounds.append(outbound)
            inserted = True
        else:
            new_outbounds.append(out)
    if not inserted:
        new_outbounds.append(outbound)
    template["outbounds"] = new_outbounds

    routing = template.setdefault("routing", {})
    filtered_rules = []
    for rule in routing.get("rules", []):
        if _is_ai_quic_block_rule(rule):
            continue
        updated_rule = dict(rule)
        if updated_rule.get("outboundTag") == "warp-socks":
            updated_rule["outboundTag"] = "warp-wireguard"
        filtered_rules.append(updated_rule)
    routing["rules"] = filtered_rules

    write_secure_json(template_path, template)


def main():
    parser = argparse.ArgumentParser(description="Cloudflare WARP Native WireGuard Outbound Generator")
    parser.add_argument("--output", "-o", help="Path to write outbound JSON configuration")
    parser.add_argument("--update-template", "-t", help="Path to xray_template_config.json to update in-place")
    parser.add_argument("--print-json", "-p", action="store_true", help="Print outbound JSON to stdout")
    args = parser.parse_args()

    try:
        priv_b64, pub_b64 = generate_keypair()
        reg_data = register_warp(pub_b64)
        outbound = build_xray_outbound(priv_b64, reg_data)

        if args.print_json or (not args.output and not args.update_template):
            print(json.dumps(outbound, indent=2))
        if args.output:
            write_secure_json(args.output, outbound)
            print(f"[+] Outbound configuration saved to {args.output}")
        if args.update_template:
            apply_outbound_to_template(args.update_template, outbound)
            print(f"[+] Successfully updated {args.update_template} with native WireGuard outbound")
    except Exception as e:
        print(f"[-] WARP WireGuard generation failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
