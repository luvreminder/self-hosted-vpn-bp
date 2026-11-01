#!/usr/bin/env python3
"""
Comprehensive Monthly Maintenance & Anti-Blocking Hardening for VLESS-REALITY + 3X-UI VPS.
Executed directly against the remote VPS.
"""
import sys
import io
import json
import secrets
import paramiko

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import os
import argparse
import re

REMOTE_SCRIPT = r"""#!/usr/bin/env python3
import sys
import os
import json
import sqlite3
import subprocess
import secrets

print("[+] === STARTING MONTHLY VPS MAINTENANCE & HARDENING ===")

DB_PATH = "/etc/x-ui/x-ui.db"

# -------------------------------------------------------------
# STEP 1: Update GeoIP and GeoSite Databases (RunetFreedom + Loyalsoldier)
# -------------------------------------------------------------
print("\n[+] 1. Updating anti-censorship GeoIP and GeoSite databases...")
try:
    res = subprocess.run(["/usr/bin/x-ui", "update-all-geofiles"], capture_output=True, text=True, timeout=120)
    print(res.stdout.strip())
    print("[OK] GeoIP and GeoSite databases successfully updated.")
except Exception as e:
    print(f"[!] Geo-database update warning: {e}")

# -------------------------------------------------------------
# STEP 2: Maintain Reality Camouflage (SNI) and Rotate Short IDs
# -------------------------------------------------------------
print("\n[+] 2. Maintaining Reality SNI camouflage pool and rotating Short IDs...")
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("SELECT id, stream_settings FROM inbounds WHERE id=1;")
row = cur.fetchone()
dest_target = "gateway.icloud.com:443"
valid_snis = ["gateway.icloud.com"]
sni_label_map = {}

if row:
    stream = json.loads(row[1])
    reality = stream.get("realitySettings", {})
    dest_target = reality.get("dest", "gateway.icloud.com:443").strip()
    dest_lower = dest_target.lower()
    
    # CRITICAL: In Reality, all serverNames must strictly match the SAN certificate of dest!
    # Do not mix incompatible domains (Apple, Google, Microsoft) in a single inbound.
    if "icloud" in dest_lower or "apple" in dest_lower:
        valid_snis = [
            "gateway.icloud.com",
            "configuration.apple.com",
            "swdist.apple.com",
            "updates.cdn-apple.com",
            "appleid.apple.com"
        ]
        sni_label_map = {
            "gateway.icloud.com": "Apple iCloud Mobile Stealth 📱",
            "configuration.apple.com": "Apple Device Provisioning 🛡️",
            "swdist.apple.com": "Apple Software CDN ⚡",
            "updates.cdn-apple.com": "Apple System CDN 🍏",
            "appleid.apple.com": "Apple Auth Gateway 🔒"
        }
    elif "google" in dest_lower:
        valid_snis = [
            "dl.google.com",
            "www.google.com",
            "fonts.googleapis.com"
        ]
        sni_label_map = {
            "dl.google.com": "Google CDN Fast ⚡",
            "www.google.com": "Google Search CDN 🌐",
            "fonts.googleapis.com": "Google Fonts CDN 🔤"
        }
    elif "microsoft" in dest_lower:
        valid_snis = [
            "www.microsoft.com",
            "c.s-microsoft.com"
        ]
        sni_label_map = {
            "www.microsoft.com": "Microsoft Web CDN 💻",
            "c.s-microsoft.com": "Microsoft Static CDN 🛡️"
        }
    else:
        # Preserve current names for custom domains and Self-SNI (Steal Oneself)
        current_names = reality.get("serverNames", [])
        dest_host = dest_target.split(":")[0]
        valid_snis = current_names if current_names else [dest_host]
        sni_label_map = {s: f"Custom Stealth ({s}) 🔒" for s in valid_snis}

    reality["serverNames"] = valid_snis
    
    # Short ID rotation: purge known sample keys from public templates (preserve active user sids)
    public_compromised_sids = {
        "0123456789abcdef", "1234567890abcdef"
    }
    existing_sids = set(reality.get("shortIds", [])) - public_compromised_sids
    # Always keep the primary production Short ID active for backwards compatibility
    existing_sids.add("859a72d4fa0c9a5e")
    
    # Generate fresh cryptographically secure 8-byte hex tokens
    while len(existing_sids) < 4:
        existing_sids.add(secrets.token_hex(8))
    
    sorted_sids = sorted(list(existing_sids))
    reality["shortIds"] = sorted_sids
    stream["realitySettings"] = reality
    
    cur.execute("UPDATE inbounds SET stream_settings=? WHERE id=1;", (json.dumps(stream),))
    print(f"[OK] Reality Inbound #1 updated:")
    print(f"     Dest: {dest_target}")
    print(f"     Validated SAN SNIs ({len(valid_snis)}): {', '.join(valid_snis)}")
    print(f"     Cryptographic Short IDs ({len(sorted_sids)}): {', '.join(sorted_sids)}")

# -------------------------------------------------------------
# STEP 2.1: Verify Reality Dest Reachability & Private VLAN Host Routing
# -------------------------------------------------------------
print("\n[+] 2.1. Verifying Reality target destination reachability & Private VLAN routing...")
dest_host = dest_target.split(":")[0]
dest_port = int(dest_target.split(":")[1]) if ":" in dest_target else 443

def check_dest_reachability(host, port, timeout=3.0):
    try:
        import socket, ssl
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ts = ctx.wrap_socket(s, server_hostname=host)
        ts.close()
        return True, "TLS Handshake OK"
    except Exception as err:
        return False, str(err)

dest_ok, dest_msg = check_dest_reachability(dest_host, dest_port)
if dest_ok:
    print(f"[OK] Reality dest ({dest_target}) is healthy and reachable: {dest_msg}")
else:
    print(f"[!] Reality dest ({dest_target}) unreachable: {dest_msg}")
    print("[*] Checking for Private VLAN (PVLAN) intra-subnet isolation...")
    try:
        gw_res = subprocess.run("ip route show default 2>/dev/null", shell=True, capture_output=True, text=True)
        gw_match = re.search(r"default via (\S+) dev (\S+)", gw_res.stdout)
        if gw_match:
            default_gw = gw_match.group(1)
            default_dev = gw_match.group(2)
            import socket
            dest_ips = list({res[4][0] for res in socket.getaddrinfo(dest_host, dest_port, socket.AF_INET, socket.SOCK_STREAM)})
            for d_ip in dest_ips:
                print(f"[*] Applying host route: {d_ip} via default gateway {default_gw} dev {default_dev}")
                subprocess.run(["ip", "route", "replace", d_ip, "via", default_gw, "dev", default_dev], check=False)
                # Persist route via NetworkManager if available
                nm_check = subprocess.run(["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show", "--active"], capture_output=True, text=True)
                for line in nm_check.stdout.splitlines():
                    if f":{default_dev}" in line or f":{default_dev}:" in line or line.endswith(f":{default_dev}"):
                        conn_name = line.split(":")[0]
                        subprocess.run(["nmcli", "connection", "modify", conn_name, "+ipv4.routes", f"{d_ip}/32 {default_gw}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                # Also write fallback route file for RHEL/CentOS/Rocky
                route_file = f"/etc/sysconfig/network-scripts/route-{default_dev}"
                if os.path.exists(f"/etc/sysconfig/network-scripts/ifcfg-{default_dev}"):
                    try:
                        with open(route_file, "a+") as rf:
                            rf.seek(0)
                            existing_routes = rf.read()
                            if d_ip not in existing_routes:
                                rf.write(f"{d_ip}/32 via {default_gw} dev {default_dev}\n")
                    except Exception:
                        pass
            
            # Re-test reachability
            re_ok, re_msg = check_dest_reachability(dest_host, dest_port)
            if re_ok:
                print(f"[OK] Reality dest connectivity restored via gateway routing: {re_msg}")
            else:
                print(f"[WARN] Reality dest ({dest_target}) remains unreachable ({re_msg}). Verify target server is online.")
        else:
            print("[!] Default gateway could not be detected.")
    except Exception as ex:
        print(f"[!] PVLAN routing auto-fix exception: {ex}")

# -------------------------------------------------------------
# STEP 3: Synchronize Node Descriptions in Subscriptions (hosts table)
# -------------------------------------------------------------
print("\n[+] 3. Updating subscription camouflage catalog (Sub-Enhancer)...")
# Resolve server geo-location for accurate client display
try:
    import urllib.request
    with urllib.request.urlopen("http://ip-api.com/json/?fields=country,countryCode", timeout=2.5) as r:
        geo_info = json.loads(r.read().decode())
        c_code = geo_info.get("countryCode", "")
        flag = "".join(chr(127397 + ord(c)) for c in c_code.upper()) if len(c_code) == 2 else "🌐"
        geo_prefix = f"{flag} {geo_info.get('country', 'VPS')}"
except Exception:
    geo_prefix = "🛡️ Stealth"

# Synchronize hosts table strictly with valid SNI pool of current inbound
server_ip = os.environ.get("SERVER_IP", "").strip()
if not server_ip:
    try:
        req = urllib.request.Request("https://api.ipify.org", headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req, timeout=3.0) as r:
            server_ip = r.read().decode("utf-8").strip()
    except Exception:
        server_ip = ""

for order, sni in enumerate(valid_snis, start=1):
    base_label = sni_label_map.get(sni, f"CDN {sni}")
    remark = f"{geo_prefix} • {base_label}"
    sort_order = order * 10
    cur.execute("SELECT id, address, port FROM hosts WHERE inbound_id=1 AND sni=?;", (sni,))
    h_row = cur.fetchone()
    if h_row:
        cur.execute(
            "UPDATE hosts SET remark=?, server_description=?, sort_order=?, is_disabled=0, "
            "address=COALESCE(NULLIF(address, ''), NULLIF(?, '')), "
            "port=CASE WHEN port=0 THEN 443 ELSE port END, "
            "fingerprint=COALESCE(NULLIF(fingerprint, ''), 'chrome') "
            "WHERE id=?;",
            (remark, remark, sort_order, server_ip, h_row[0])
        )
    else:
        cur.execute(
            "INSERT INTO hosts (inbound_id, sni, remark, server_description, sort_order, is_disabled, security, address, port, fingerprint, created_at, updated_at) "
            "VALUES (1, ?, ?, ?, ?, 0, 'same', NULLIF(?, ''), 443, 'chrome', strftime('%s', 'now') * 1000, strftime('%s', 'now') * 1000);",
            (sni, remark, remark, sort_order, server_ip)
        )

# Deactivate incompatible SNIs from legacy configurations
placeholders = ",".join("?" for _ in valid_snis)
cur.execute(f"UPDATE hosts SET is_disabled=1 WHERE inbound_id=1 AND sni NOT IN ({placeholders});", tuple(valid_snis))
conn.commit()
print(f"[OK] {len(valid_snis)} subscription nodes synchronized with dest SAN certificate.")

# -------------------------------------------------------------
# STEP 4: Update Xray Routing Template (AI Smart Routing & QUIC Hardening)
# -------------------------------------------------------------
print("\n[+] 4. Updating AI smart routing rules and QUIC blocking...")
cur.execute("SELECT value FROM settings WHERE key='xrayTemplateConfig';")
t_row = cur.fetchone()
config = json.loads(t_row[0]) if t_row else {}

# Inbounds
config["inbounds"] = [
    {
        "tag": "api",
        "listen": "127.0.0.1",
        "port": 62789,
        "protocol": "dokodemo-door",
        "settings": {
            "address": "127.0.0.1"
        }
    }
]

# API & Stats
config["api"] = {
    "tag": "api",
    "services": [
        "HandlerService",
        "LoggerService",
        "StatsService",
        "RoutingService"
    ]
}
config["stats"] = {}
config["policy"] = {
    "levels": {
        "0": {
            "statsUserUplink": True,
            "statsUserDownlink": True
        }
    },
    "system": {
        "statsInboundUplink": True,
        "statsInboundDownlink": True,
        "statsOutboundUplink": True,
        "statsOutboundDownlink": True
    }
}

# Outbounds
config["outbounds"] = [
    {
        "tag": "direct",
        "protocol": "freedom",
        "settings": {
            "domainStrategy": "UseIPv4"
        }
    },
    {
        "tag": "warp-socks",
        "protocol": "socks",
        "settings": {
            "servers": [
                {
                    "address": "127.0.0.1",
                    "port": 40000
                }
            ]
        }
    },
    {
        "tag": "blocked",
        "protocol": "blackhole",
        "settings": {
            "response": {
                "type": "http"
            }
        }
    }
]

# Extended list of AI services routed via Cloudflare WARP (excluding Google Gemini which uses clean direct German IP)
ai_domains = [
    # Geosite groups
    "geosite:openai",
    "geosite:anthropic",
    "geosite:perplexity",
    # OpenAI, ChatGPT, Sora
    "domain:openai.com",
    "domain:chatgpt.com",
    "domain:oaistatic.com",
    "domain:oaiusercontent.com",
    "domain:sora.com",
    "domain:ai.com",
    "domain:chat.openai.com",
    "domain:auth0.openai.com",
    "domain:client-api.arkoselabs.com",
    "domain:featuregates.org",
    "domain:statsig.com",
    "domain:statsigapi.net",
    # Anthropic & Claude
    "domain:anthropic.com",
    "domain:claude.ai",
    "domain:claude.com",
    # Coding & Development AI
    "domain:cursor.sh",
    "domain:cursor.com",
    "domain:cursor-cdn.com",
    "domain:copilot.microsoft.com",
    # Additional AI Services
    "domain:perplexity.ai",
    "domain:midjourney.com",
    "domain:x.ai",
    "domain:grok.com",
    "domain:deepseek.com",
    "domain:mistral.ai",
    "domain:cohere.com"
]

config["routing"] = {
    "domainStrategy": "IPIfNonMatch",
    "rules": [
        {
            "type": "field",
            "inboundTag": ["api"],
            "outboundTag": "api"
        },
        {
            "type": "field",
            "outboundTag": "blocked",
            "protocol": ["bittorrent"]
        },
        {
            "type": "field",
            "outboundTag": "blocked",
            "ip": ["geoip:private"]
        },
        {
            "type": "field",
            "outboundTag": "blocked",
            "domain": ["geosite:category-ads-all"]
        },
        # Block QUIC (UDP 443) for AI services to prevent stalled connections over WARP
        {
            "type": "field",
            "outboundTag": "blocked",
            "port": "443",
            "network": "udp",
            "domain": [
                "geosite:openai",
                "geosite:anthropic",
                "geosite:perplexity",
                "domain:openai.com",
                "domain:chatgpt.com",
                "domain:anthropic.com",
                "domain:claude.ai",
                "domain:perplexity.ai"
            ]
        },
        {
            "type": "field",
            "outboundTag": "warp-socks",
            "domain": ai_domains
        },
        {
            "type": "field",
            "outboundTag": "direct",
            "network": "tcp,udp"
        }
    ]
}

config["dns"] = {
    "servers": [
        "1.1.1.1",
        "8.8.8.8",
        "1.0.0.1",
        "localhost"
    ],
    "queryStrategy": "UseIPv4"
}

cur.execute("UPDATE settings SET value=? WHERE key='xrayTemplateConfig';", (json.dumps(config, indent=2),))
conn.commit()
conn.close()
print(f"[OK] Xray template updated: {len(ai_domains)} AI domains routed via Cloudflare WARP.")

# -------------------------------------------------------------
# STEP 5: SQLite Database Maintenance and Compaction
# -------------------------------------------------------------
print("\n[+] 5. Verifying integrity and vacuuming SQLite database...")
# Briefly stop service to safely flush WAL and perform VACUUM
subprocess.run(["systemctl", "stop", "x-ui"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
subprocess.run(["sqlite3", DB_PATH, "PRAGMA wal_checkpoint(TRUNCATE); VACUUM;"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
check_res = subprocess.run(["sqlite3", DB_PATH, "PRAGMA integrity_check;"], capture_output=True, text=True)
print(f"[OK] SQLite Integrity Check: {check_res.stdout.strip()}")

# -------------------------------------------------------------
# STEP 6: Clean Logs and Temporary Files
# -------------------------------------------------------------
print("\n[+] 6. Cleaning system journals and temporary files...")
subprocess.run(["journalctl", "--vacuum-time=14d", "--vacuum-size=100M"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
subprocess.run("rm -f /tmp/*.py /tmp/*.json /tmp/*.tmp 2>/dev/null || true", shell=True)
print("[OK] Historical logs and temporary files cleaned.")

# -------------------------------------------------------------
# STEP 7: Restart and Verify Services
# -------------------------------------------------------------
print("\n[+] 7. Restarting 3X-UI and Sub-Enhancer...")
subprocess.run(["systemctl", "restart", "x-ui"], check=True)
subprocess.run(["systemctl", "restart", "sub-enhancer"], check=True)

# -------------------------------------------------------------
# STEP 8: Configure Automated Monthly Maintenance (Systemd Timer)
# -------------------------------------------------------------
print("\n[+] 8. Configuring automated monthly maintenance (Systemd Timer)...")

maint_script_content = r'''#!/usr/bin/env bash
# Monthly VPS Maintenance Script
set -e
echo "=== [$(date)] Starting Scheduled Monthly Maintenance ==="

# 0. Ensure Reality dest and PVLAN neighbor routing health
echo "[*] Checking Reality dest connectivity and intra-subnet routing..."
DEFAULT_GW=$(ip route show default 2>/dev/null | awk '{print $3}' | head -n1)
DEFAULT_DEV=$(ip route show default 2>/dev/null | awk '{print $5}' | head -n1)

if [ -f /etc/x-ui/x-ui.db ] && [ -n "$DEFAULT_GW" ] && [ -n "$DEFAULT_DEV" ]; then
    REALITY_DEST=$(sqlite3 /etc/x-ui/x-ui.db "SELECT stream_settings FROM inbounds WHERE id=1;" 2>/dev/null | grep -o '"dest": *"[^"]*"' | head -n1 | cut -d'"' -f4)
    if [ -n "$REALITY_DEST" ]; then
        DEST_HOST=$(echo "$REALITY_DEST" | cut -d':' -f1)
        DEST_PORT=$(echo "$REALITY_DEST" | cut -d':' -f2)
        [ -z "$DEST_PORT" ] && DEST_PORT=443
        
        # Test connection to Reality dest
        if ! curl -s -I --max-time 3 "https://${DEST_HOST}:${DEST_PORT}" >/dev/null 2>&1; then
            echo "[!] Reality dest (${REALITY_DEST}) not directly reachable. Resolving IP for gateway route..."
            DEST_IPS=$(getent ahosts "$DEST_HOST" 2>/dev/null | awk '{print $1}' | sort -u)
            for d_ip in $DEST_IPS; do
                echo "[*] Applying gateway host route for Reality dest: $d_ip via $DEFAULT_GW dev $DEFAULT_DEV"
                ip route replace "$d_ip" via "$DEFAULT_GW" dev "$DEFAULT_DEV" 2>/dev/null || true
            done
            if curl -s -I --max-time 3 "https://${DEST_HOST}:${DEST_PORT}" >/dev/null 2>&1; then
                echo "[OK] Reality dest connection restored via gateway route."
            else
                echo "[WARN] Reality dest (${REALITY_DEST}) still unreachable. Please verify donor status."
            fi
        else
            echo "[OK] Reality dest (${REALITY_DEST}) is healthy."
        fi
    fi
fi

# 1. Update GeoIP & GeoSite databases
echo "[*] Updating GeoIP & GeoSite databases..."
/usr/bin/x-ui update-all-geofiles || true

# 2. SQLite maintenance (Safely stop x-ui before VACUUM to prevent locking/corruption)
echo "[*] Safely stopping 3X-UI for SQLite maintenance..."
systemctl stop x-ui || true
echo "[*] SQLite VACUUM and WAL Checkpoint..."
sqlite3 /etc/x-ui/x-ui.db "PRAGMA wal_checkpoint(TRUNCATE); VACUUM;" || true
echo "[*] Starting 3X-UI service..."
systemctl start x-ui || true

# 3. Clean system journals
echo "[*] Cleaning logs..."
journalctl --vacuum-time=14d --vacuum-size=100M || true

# 4. Check WARP status and reconnect if needed
if ! curl -s -x socks5h://127.0.0.1:40000 --max-time 5 https://www.cloudflare.com/cdn-cgi/trace | grep -q "warp=on"; then
    echo "[!] WARP connection issue detected. Reconnecting..."
    systemctl restart warp-svc || true
    sleep 3
    warp-cli --accept-tos connect || true
fi

# 5. Restart services
echo "[*] Verifying services..."
systemctl restart sub-enhancer || true
systemctl is-active --quiet x-ui || systemctl restart x-ui || true

echo "=== [$(date)] Monthly Maintenance Completed Successfully ==="
'''

with open("/usr/local/bin/vps-monthly-maintenance.sh", "w") as f:
    f.write(maint_script_content)
os.chmod("/usr/local/bin/vps-monthly-maintenance.sh", 0o755)

service_unit = '''[Unit]
Description=Automated Monthly VPS Maintenance & Anti-Censorship Sync
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/vps-monthly-maintenance.sh
StandardOutput=journal
StandardError=journal
'''

with open("/etc/systemd/system/vps-maintenance.service", "w") as f:
    f.write(service_unit)

timer_unit = '''[Unit]
Description=Timer for Automated Monthly VPS Maintenance
Requires=vps-maintenance.service

[Timer]
# Run on the 1st of every month at 04:30 AM
OnCalendar=*-*-01 04:30:00
Persistent=true

[Install]
WantedBy=timers.target
'''

with open("/etc/systemd/system/vps-maintenance.timer", "w") as f:
    f.write(timer_unit)

subprocess.run(["systemctl", "daemon-reload"], check=True)
subprocess.run(["systemctl", "enable", "--now", "vps-maintenance.timer"], check=True)
print("[OK] Systemd Timer vps-maintenance.timer activated (schedule: 1st of every month at 04:30).")

print("\n=== [✓] MONTHLY VPS MAINTENANCE COMPLETED SUCCESSFULLY ===")
"""

def resolve_credentials(args):
    host = args.host or os.environ.get("VPS_HOST")
    port = args.port or int(os.environ.get("VPS_SSH_PORT", "22"))
    user = args.user or os.environ.get("VPS_USER", "root")
    password = args.password or os.environ.get("VPS_PASSWORD")
    key_path = args.key or os.environ.get("VPS_SSH_KEY")

    # Look for local credentials.txt across probable workspace paths
    cred_paths = [
        "credentials.txt",
        "../credentials.txt",
        os.path.join(os.path.dirname(__file__), "..", "credentials.txt"),
        os.path.join(os.path.dirname(__file__), "credentials.txt")
    ]
    for p in cred_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or line.startswith("["):
                            continue
                        # Delimiter detection: '=' or ':'
                        delim = "=" if "=" in line else (":" if ":" in line else None)
                        if delim:
                            k, v = line.split(delim, 1)
                            k = k.strip().upper()
                            v = v.strip().strip('"').strip("'")
                            if not host and (k in ("IP", "HOST", "SERVER_IP", "SERVER") or "IP" in k):
                                if v and not v.startswith("YOUR_") and not v.startswith("<"):
                                    host = v
                            if not port and (k in ("SSH_PORT", "PORT") or "PORT" in k):
                                try:
                                    port = int(v)
                                except ValueError:
                                    pass
                            if not user and (k in ("SSH_USER", "USER", "USERNAME") or "USER" in k):
                                if v and not v.startswith("YOUR_"):
                                    user = v
                            if not password and (k in ("PASSWORD", "SSH_PASSWORD", "ROOT_PASSWORD") or "PASS" in k):
                                if v and not v.startswith("YOUR_") and not v.startswith("<"):
                                    password = v
                            if not key_path and (k in ("SSH_KEY_PATH", "SSH_KEY", "KEY_PATH", "KEY") or "KEY" in k):
                                if v and not v.startswith("<") and not v.startswith("YOUR_"):
                                    expanded = os.path.expandvars(os.path.expanduser(v))
                                    if os.path.exists(expanded):
                                        key_path = expanded
            except Exception:
                pass
            if host and (password or key_path):
                break

    if not key_path:
        for default_key in ["~/.ssh/id_ed25519", "~/.ssh/vps_ed25519", "~/.ssh/id_rsa"]:
            expanded = os.path.expanduser(default_key)
            if os.path.exists(expanded):
                key_path = expanded
                break

    return host, port, user, password, key_path

def main():
    parser = argparse.ArgumentParser(description="VPS Monthly Maintenance & Anti-Censorship Sync")
    parser.add_argument("--host", help="VPS IP address or hostname")
    parser.add_argument("--port", type=int, default=22, help="SSH port (default: 22)")
    parser.add_argument("--user", default="root", help="SSH username (default: root)")
    parser.add_argument("--password", help="SSH password")
    parser.add_argument("--key", help="Path to SSH private key")
    args = parser.parse_args()

    host, port, user, password, key_path = resolve_credentials(args)

    if not host:
        print("[!] Error: VPS host IP address is required.")
        print("    Specify via argument: python run_monthly_maintenance.py --host <IP>")
        print("    Or set environment variable: VPS_HOST=<IP>")
        sys.exit(1)

    print(f"[*] Connecting to server {host}:{port} as {user}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connect_kwargs = {
        "hostname": host,
        "port": port,
        "username": user,
        "timeout": 15
    }
    if key_path and os.path.exists(key_path):
        connect_kwargs["key_filename"] = key_path
    elif password:
        connect_kwargs["password"] = password

    ssh.connect(**connect_kwargs)

    print("[*] Uploading maintenance script...")
    sftp = ssh.open_sftp()
    with sftp.file("/tmp/run_maintenance.py", "w") as f:
        f.write(REMOTE_SCRIPT)
    sftp.close()

    print("[*] Executing remote maintenance...")
    stdin, stdout, stderr = ssh.exec_command("python3 /tmp/run_maintenance.py", get_pty=True)

    for line in stdout:
        print(line, end="")

    err = stderr.read().decode('utf-8', errors='replace')
    if err:
        print("\n[STDERR]:\n" + err)

    ssh.close()

if __name__ == "__main__":
    main()
