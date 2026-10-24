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

def build_xray_outbound(priv_b64, reg_response):
    """Constructs Xray Core native WireGuard outbound configuration object."""
    config = reg_response.get("result", {}).get("config", {})
    if not config:
        config = reg_response.get("config", {})

    v4_addr = config.get("interface", {}).get("addresses", {}).get("v4", "192.0.2.2")
    if not v4_addr.endswith("/32"):
        v4_addr = f"{v4_addr}/32"

    v6_addr = config.get("interface", {}).get("addresses", {}).get("v6", "")
    addresses = [v4_addr]
    if v6_addr:
        if not v6_addr.endswith("/128"):
            v6_addr = f"{v6_addr}/128"
        addresses.append(v6_addr)

    client_id_raw = config.get("client_id", "")
    if client_id_raw:
        try:
            reserved = list(base64.b64decode(client_id_raw))
        except Exception:
            reserved = [0, 0, 0]
    else:
        reserved = [0, 0, 0]

    peers = config.get("peers", [])
    peer_pub = "bmXOC+F1FxEMF9dyiK2H5/1SUtzH0JuVo51h2wPfgyo="
    peer_endpoint = "engage.cloudflareclient.com:2408"

    if peers:
        p = peers[0]
        peer_pub = p.get("public_key", peer_pub)
        endpoint_obj = p.get("endpoint", {})
        if isinstance(endpoint_obj, dict):
            host = endpoint_obj.get("host", "engage.cloudflareclient.com:2408")
            if host:
                peer_endpoint = host
        elif isinstance(endpoint_obj, str) and endpoint_obj:
            peer_endpoint = endpoint_obj

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
            os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(outbound, f, indent=2)
            print(f"[+] Outbound configuration saved to {args.output}")

        if args.update_template:
            if os.path.exists(args.update_template):
                with open(args.update_template, "r", encoding="utf-8") as f:
                    template = json.load(f)

                outbounds = template.get("outbounds", [])
                # Replace existing warp outbound or append
                replaced = False
                for idx, out in enumerate(outbounds):
                    if out.get("tag") in ("warp-socks", "warp-wireguard"):
                        outbounds[idx] = outbound
                        replaced = True
                        break
                if not replaced:
                    outbounds.append(outbound)
                template["outbounds"] = outbounds

                # Update routing rules to route to warp-wireguard and remove UDP:443 AI block
                rules = template.get("routing", {}).get("rules", [])
                filtered_rules = []
                for r in rules:
                    # Remove the blocked rule for UDP:443 on AI domains since WireGuard handles UDP natively
                    if r.get("outboundTag") == "blocked" and r.get("network") == "udp" and r.get("port") == "443":
                        continue
                    if r.get("outboundTag") == "warp-socks":
                        r["outboundTag"] = "warp-wireguard"
                    filtered_rules.append(r)
                template["routing"]["rules"] = filtered_rules

                with open(args.update_template, "w", encoding="utf-8") as f:
                    json.dump(template, f, indent=2)
                print(f"[+] Successfully updated {args.update_template} with native WireGuard outbound")
            else:
                print(f"[-] Error: Template file {args.update_template} not found", file=sys.stderr)
                sys.exit(1)

    except Exception as e:
        print(f"[-] WARP WireGuard generation failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
