#!/usr/bin/env bash
# ==============================================================================
# 🌐 Golden Standard VPN Infrastructure Automated Installer
# Target OS: Rocky Linux 9, AlmaLinux 9, Ubuntu 22.04/24.04, Debian 12
# Virtualization Requirement: KVM / VMware / Bare-metal (OpenVZ/LXC unsupported)
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKIP_SWAP=false
SKIP_WARP=false
NATIVE_WARP=true
SINGLE_PORT_443=false
ENABLE_HYSTERIA=false
CHECK_ONLY=false
STEALTH_ICMP=false
SUB_PORTS="${SUB_PORTS:-2096,28443,80}"

show_help() {
    cat << 'EOF'
Usage: sudo ./universal_deploy.sh [OPTIONS]

Options:
  -h, --help            Show this help message and exit.
  -c, --check           Run environment and hardware compatibility checks without modifying the system.
  --skip-swap           Skip automatic 2 GB swapfile allocation.
  --skip-warp           Skip Cloudflare WARP deployment entirely.
  --native-warp         Deploy lightweight native WireGuard outbound in Xray (default, 0 MB daemon RAM).
  --legacy-warp         Deploy official Cloudflare WARP daemon in SOCKS5 proxy mode (port 40000).
  --single-port-443     Enforce Next-Gen Single Port 443 architecture (closes 2096, 28443, 8443, 2083; SNI demux).
  --enable-hysteria     Enable Hysteria 2 / QUIC UDP 443 and port hopping range (20000-50000/udp).
  --stealth-icmp        Enable silent ICMP blackhole mode (drops ping; hides from mass sweeps). Default is active ICMP (Stack Mimicry).
  --keep-icmp           (Deprecated alias) Keep standard ICMP echo responses active.
  --sub-ports PORTS     Custom comma-separated subscription gateway ports (default: 2096,28443,80).

Documentation: README.md
EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            show_help
            exit 0
            ;;
        -c|--check)
            CHECK_ONLY=true
            shift
            ;;
        --skip-swap)
            SKIP_SWAP=true
            shift
            ;;
        --skip-warp)
            SKIP_WARP=true
            shift
            ;;
        --native-warp)
            NATIVE_WARP=true
            shift
            ;;
        --legacy-warp)
            NATIVE_WARP=false
            shift
            ;;
        --single-port-443)
            SINGLE_PORT_443=true
            shift
            ;;
        --enable-hysteria)
            ENABLE_HYSTERIA=true
            shift
            ;;
        --stealth-icmp)
            STEALTH_ICMP=true
            shift
            ;;
        --keep-icmp)
            STEALTH_ICMP=false
            shift
            ;;
        --sub-ports)
            if [[ $# -lt 2 || -z "${2:-}" ]]; then
                echo "❌ Error: --sub-ports requires a comma-separated port list." >&2
                exit 1
            fi
            SUB_PORTS="$2"
            shift 2
            ;;
        *)
            echo "❌ Unknown option: $1" >&2
            show_help
            exit 1
            ;;
    esac
done

echo "=========================================================="
echo "🚀 Launching Golden Standard VPN Automated Deployment"
echo "=========================================================="

# 1. Root privilege verification
if [ "$(id -u)" -ne 0 ]; then
    echo "❌ Error: This deployment script must be run as root (use sudo)." >&2
    exit 1
fi

# 2. Virtualization platform verification
VIRT_TYPE=$(systemd-detect-virt || echo "unknown")
echo "🔍 Hypervisor detected: $VIRT_TYPE"
if [ "$VIRT_TYPE" = "openvz" ] || [ "$VIRT_TYPE" = "lxc" ]; then
    echo "❌ Error: Unsupported container virtualization detected ($VIRT_TYPE)." >&2
    echo "   TCP BBR congestion control, tun adapters, and Cloudflare WARP require KVM or bare-metal." >&2
    exit 1
fi
echo "✅ Hypervisor check passed ($VIRT_TYPE)."

# 3. CPU Architecture verification
CPU_ARCH=$(uname -m)
echo "🔍 CPU Architecture: $CPU_ARCH"
if [ "$CPU_ARCH" != "x86_64" ] && [ "$CPU_ARCH" != "aarch64" ]; then
    echo "❌ Error: Unsupported CPU architecture: $CPU_ARCH. Expected x86_64 or aarch64." >&2
    exit 1
fi
echo "✅ CPU Architecture verified."

# 4. Operating system detection and validation
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_ID=$ID
    OS_VER=${VERSION_ID%%.*}
else
    echo "❌ Error: Unable to detect operating system distribution (/etc/os-release missing)." >&2
    exit 1
fi

echo "📦 Detected Operating System: ${NAME:-$OS_ID} ($OS_ID $VERSION_ID)"

case "$OS_ID" in
    rocky|almalinux|rhel|centos)
        if [ "$OS_VER" -lt 9 ]; then
            echo "❌ Error: $OS_ID version $OS_VER is not supported." >&2
            echo "   Rocky Linux 9 or AlmaLinux 9 is required (Kernel 5.14+, glibc 2.34+, official WARP support)." >&2
            exit 1
        fi
        ;;
    ubuntu)
        if [ "$OS_VER" -lt 22 ]; then
            echo "❌ Error: Ubuntu version $VERSION_ID is not supported. Ubuntu 22.04 LTS or newer is required." >&2
            exit 1
        fi
        ;;
    debian)
        if [ "$OS_VER" -lt 12 ]; then
            echo "❌ Error: Debian version $VERSION_ID is not supported. Debian 12 (Bookworm) or newer is required." >&2
            exit 1
        fi
        ;;
    *)
        echo "⚠️ Warning: Distribution $OS_ID has not been certified. Proceeding with caution..."
        ;;
esac

# Pre-flight check termination if requested
if [ "$CHECK_ONLY" = true ]; then
    echo "=========================================================="
    echo "✅ Pre-flight checks completed: System is fully compatible."
    TOTAL_MEM_MB=$(grep MemTotal /proc/meminfo | awk '{print int($2/1024)}')
    echo "   Physical RAM: ${TOTAL_MEM_MB} MB"
    echo "   Hypervisor:   $VIRT_TYPE"
    echo "   OS Release:   $OS_ID $VERSION_ID"
    echo "=========================================================="
    exit 0
fi

# 5. Swap allocation (Ensures stability on 1 GB RAM VPS nodes)
TOTAL_MEM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
if [ "$SKIP_SWAP" = false ] && [ "$TOTAL_MEM_KB" -le 1500000 ] && [ "$(swapon --show | wc -l)" -le 1 ]; then
    echo "💾 Creating 2 GB Swap file to prevent Out-Of-Memory termination..."
    fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    if ! grep -q '/swapfile' /etc/fstab; then
        echo '/swapfile none swap sw 0 0' >> /etc/fstab
    fi
    echo "✅ Swap allocation completed."
fi

# 6. Package dependencies installation
echo "📦 Installing core system packages..."
case "$OS_ID" in
    ubuntu|debian)
        export DEBIAN_FRONTEND=noninteractive
        apt update -y
        apt install -y curl wget git jq sqlite3 iptables python3 python3-pip gpg lsb-release ca-certificates
        if [ "$SINGLE_PORT_443" = true ]; then
            apt install -y nginx libnginx-mod-stream || apt install -y nginx
        fi
        # Install iptables persistence utility non-interactively
        echo iptables-persistent iptables-persistent/autosave_v4 boolean true | debconf-set-selections || true
        echo iptables-persistent iptables-persistent/autosave_v6 boolean true | debconf-set-selections || true
        apt install -y iptables-persistent || true
        ;;
    rocky|almalinux|rhel|centos)
        dnf install -y epel-release || true
        dnf install -y curl wget git jq sqlite iptables iptables-services python3 python3-pip ca-certificates
        if [ "$SINGLE_PORT_443" = true ]; then
            dnf install -y nginx nginx-mod-stream || dnf install -y nginx
        fi
        systemctl enable --now iptables || true
        ;;
esac

# 7. Kernel performance tuning (TCP BBR + Anti-DPI TCP KeepAlive + MTU Probing + ICMP Handling)
echo "⚡ Configuring kernel: Enabling TCP BBR, MTU Probing, TFO & Anti-DPI TCP KeepAlive..."
if [ -f /etc/sysctl.conf ]; then
    sed -i '/net.core.default_qdisc/d' /etc/sysctl.conf
    sed -i '/net.ipv4.tcp_congestion_control/d' /etc/sysctl.conf
    sed -i '/net.ipv4.tcp_keepalive_time/d' /etc/sysctl.conf
    sed -i '/net.ipv4.tcp_keepalive_intvl/d' /etc/sysctl.conf
    sed -i '/net.ipv4.tcp_keepalive_probes/d' /etc/sysctl.conf
    sed -i '/net.ipv4.tcp_mtu_probing/d' /etc/sysctl.conf
    sed -i '/net.ipv4.tcp_fastopen/d' /etc/sysctl.conf
    sed -i '/net.ipv4.icmp_echo_ignore_all/d' /etc/sysctl.conf
fi

mkdir -p /etc/sysctl.d
ICMP_IGNORE_VAL=0
if [ "$STEALTH_ICMP" = true ]; then
    ICMP_IGNORE_VAL=1
fi
cat << SYSCTL_EOF > /etc/sysctl.d/99-sota-vpn.conf
net.core.default_qdisc=fq
net.ipv4.tcp_congestion_control=bbr
net.ipv4.tcp_keepalive_time=20
net.ipv4.tcp_keepalive_intvl=5
net.ipv4.tcp_keepalive_probes=4
net.ipv4.tcp_mtu_probing=1
net.ipv4.tcp_fastopen=3
net.ipv4.icmp_echo_ignore_all=$ICMP_IGNORE_VAL
SYSCTL_EOF
sysctl --system >/dev/null 2>&1 || sysctl -p /etc/sysctl.d/99-sota-vpn.conf

# 8. Host protection against BitTorrent (Layer-7 Anti-DMCA IPv4 & IPv6) & UDP Port Hopping
echo "🛡️ Deploying Layer-7 BitTorrent packet filters (Host & Forwarding, IPv4 & IPv6)..."
FW_BINS=("iptables")
if command -v ip6tables >/dev/null 2>&1; then
    FW_BINS+=("ip6tables")
fi
for fw_bin in "${FW_BINS[@]}"; do
    for chain in OUTPUT FORWARD; do
        for proto in tcp udp; do
            for str in "BitTorrent" "BitTorrent protocol" "peer_id=" ".torrent" "announce.php?passkey="; do
                "$fw_bin" -C "$chain" -p "$proto" -m string --string "$str" --algo bm -j DROP 2>/dev/null || \
                "$fw_bin" -I "$chain" -p "$proto" -m string --string "$str" --algo bm -j DROP || true
            done
        done
    done
done

if [ "$ENABLE_HYSTERIA" = true ]; then
    echo "⚡ Configuring Layer-4 UDP port hopping for Hysteria 2 (20000:50000/udp -> 443/udp)..."
    iptables -t nat -C PREROUTING -p udp --dport 20000:50000 -j REDIRECT --to-ports 443 2>/dev/null || \
    iptables -t nat -A PREROUTING -p udp --dport 20000:50000 -j REDIRECT --to-ports 443 || true
fi

# Persist iptables & ip6tables rules across reboots
if [ "$OS_ID" = "rocky" ] || [ "$OS_ID" = "almalinux" ] || [ "$OS_ID" = "rhel" ]; then
    service iptables save || true
    if command -v ip6tables-save >/dev/null 2>&1 && [ -d /etc/sysconfig ]; then
        ip6tables-save > /etc/sysconfig/ip6tables 2>/dev/null || true
    fi
elif [ "$OS_ID" = "ubuntu" ] || [ "$OS_ID" = "debian" ]; then
    netfilter-persistent save || true
fi

# 9. Firewall rules configuration (firewalld / ufw) - Strict Default Deny
echo "🔒 Configuring firewall: Enforcing default-deny posture..."
case "$OS_ID" in
    ubuntu|debian)
        ufw default deny incoming || true
        ufw default allow outgoing || true
        ufw allow 22/tcp comment 'SSH' || true
        ufw allow 443/tcp comment 'VLESS-REALITY' || true
        if [ "$ENABLE_HYSTERIA" = true ]; then
            ufw allow 443/udp comment 'Hysteria2-QUIC' || true
            ufw allow 20000:50000/udp comment 'Hysteria2-PortHopping' || true
        fi
        if [ "$SINGLE_PORT_443" = false ]; then
            ufw allow 8443/tcp comment 'Direct-TLS' || true
            ufw allow 2083/tcp comment 'XHTTP' || true
            for p in $(echo "$SUB_PORTS" | tr ',' ' '); do
                ufw allow "${p}/tcp" comment 'Sub-Gateway' || true
            done
        fi
        ufw --force enable || true
        echo "✅ UFW configured and activated."
        ;;
    rocky|almalinux|rhel|centos)
        systemctl enable --now firewalld || true
        firewall-cmd --permanent --remove-service=cockpit 2>/dev/null || true
        firewall-cmd --permanent --add-service=ssh || true
        firewall-cmd --permanent --add-port=443/tcp || true
        if [ "$ENABLE_HYSTERIA" = true ]; then
            firewall-cmd --permanent --add-port=443/udp || true
            firewall-cmd --permanent --add-port=20000-50000/udp || true
        fi
        if [ "$SINGLE_PORT_443" = false ]; then
            firewall-cmd --permanent --add-port=8443/tcp || true
            firewall-cmd --permanent --add-port=2083/tcp || true
            for p in $(echo "$SUB_PORTS" | tr ',' ' '); do
                firewall-cmd --permanent --add-port="${p}/tcp" || true
            done
        fi
        firewall-cmd --reload || true
        echo "✅ Firewalld configured and activated."
        ;;
esac

# Initialize Xray/3X-UI paths before WARP provisioning (never mutate git-tracked template)
DB_PATH="/etc/x-ui/x-ui.db"
TEMPLATE_FILE="$SCRIPT_DIR/xray_template_config.json"
APPLIED_TEMPLATE="/etc/x-ui/xray_template_applied.json"
HOST_IP=""
mkdir -p /etc/x-ui && chmod 700 /etc/x-ui || true
if [ -f "$TEMPLATE_FILE" ]; then
    install -m 600 "$TEMPLATE_FILE" "$APPLIED_TEMPLATE"
fi

# 10. Deploy Cloudflare WARP Outbound (Native WireGuard or SOCKS5)
WARP_SUCCESS=false
if [ "$SKIP_WARP" = false ]; then
    if [ "$NATIVE_WARP" = true ]; then
        echo "🌐 Deploying Next-Gen Cloudflare WARP Native WireGuard Outbound (0 MB daemon RAM)..."
        WARP_GEN_SCRIPT="$SCRIPT_DIR/generate_warp_wireguard.py"
        if [ -f "$WARP_GEN_SCRIPT" ] && [ -f "$APPLIED_TEMPLATE" ]; then
            if python3 "$WARP_GEN_SCRIPT" --update-template "$APPLIED_TEMPLATE" --output /etc/x-ui/warp_wireguard.json; then
                echo "✅ Native WireGuard outbound registered and applied to /etc/x-ui/xray_template_applied.json."
                WARP_SUCCESS=true
            else
                echo "⚠️ Warning: Native WARP API registration failed. Falling back to legacy daemon..."
            fi
        fi
    fi

    if [ "$WARP_SUCCESS" = false ]; then
        echo "🌐 Deploying Cloudflare WARP in legacy SOCKS5 daemon mode..."
        if ! command -v warp-cli &> /dev/null; then
            case "$OS_ID" in
                ubuntu|debian)
                    curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg
                    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/cloudflare-warp.list
                    apt update -y && apt install -y cloudflare-warp
                    ;;
                rocky|almalinux|rhel|centos)
                    curl -fsSl https://pkg.cloudflareclient.com/cloudflare-warp-ascii.repo | tee /etc/yum.repos.d/cloudflare-warp.repo
                    dnf install -y cloudflare-warp
                    ;;
            esac
        fi

        systemctl enable --now warp-svc || true
        echo "⏳ Waiting for Cloudflare WARP daemon socket initialization..."
        WARP_SOCKET_READY=false
        for i in {1..15}; do
            if warp-cli --accept-tos status &>/dev/null; then
                WARP_SOCKET_READY=true
                break
            fi
            sleep 1
        done

        if [ "$WARP_SOCKET_READY" = true ]; then
            warp-cli --accept-tos register || true
            warp-cli --accept-tos set-mode proxy || true
            warp-cli --accept-tos set-proxy-port 40000 || true
            warp-cli --accept-tos connect || true
            echo "✅ Cloudflare WARP initialized on port 40000."
            WARP_SUCCESS=true
        else
            echo "⚠️ Warning: WARP socket took longer to start. You can run 'warp-cli connect' manually."
        fi
    fi
fi

# 11. Deploy 3X-UI management panel
echo "🎛️ Deploying 3X-UI management panel..."
if [ ! -d "/usr/local/x-ui" ]; then
    bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh)
fi

# 12. Enforce strict localhost isolation & apply hardened Xray routing template
HOST_IP=$(curl -s4m 3 https://api.ipify.org 2>/dev/null || curl -s4m 3 https://ifconfig.me 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || true)
[ -z "$HOST_IP" ] && HOST_IP="YOUR_SERVER_IP"
SUB_PUBLIC_IP_VAL=""
if [ "$HOST_IP" != "YOUR_SERVER_IP" ]; then
    SUB_PUBLIC_IP_VAL="$HOST_IP"
fi

# Stop x-ui to safely update database settings and prevent race conditions
systemctl stop x-ui || true

if [ -f "$DB_PATH" ]; then
    echo "🔒 Hardening 3X-UI panel: Binding strictly to 127.0.0.1:23600 (accessible only via SSH tunnel)..."
    echo "⚙️ Configuring hardened Xray Core split-routing in 3X-UI database (parameterized SQLite)..."
    python3 - "$DB_PATH" "$HOST_IP" "$APPLIED_TEMPLATE" "$WARP_SUCCESS" "$NATIVE_WARP" << 'PY_SQL_EOF'
import json
import os
import sqlite3
import sys

db_path, host_ip, applied_template, warp_success, native_warp = sys.argv[1:6]
use_native_wg = (warp_success == "true" and native_warp == "true" and os.path.exists("/etc/x-ui/warp_wireguard.json"))

ai_domains = [
    "geosite:openai", "geosite:anthropic", "geosite:perplexity",
    "domain:openai.com", "domain:chatgpt.com", "domain:oaistatic.com",
    "domain:oaiusercontent.com", "domain:sora.com", "domain:ai.com",
    "domain:chat.openai.com", "domain:auth0.openai.com",
    "domain:client-api.arkoselabs.com", "domain:featuregates.org",
    "domain:statsig.com", "domain:statsigapi.net",
    "domain:anthropic.com", "domain:claude.ai", "domain:claude.com",
    "domain:cursor.sh", "domain:cursor.com", "domain:cursor-cdn.com",
    "domain:copilot.microsoft.com", "domain:perplexity.ai",
    "domain:midjourney.com", "domain:x.ai", "domain:grok.com",
    "domain:deepseek.com", "domain:mistral.ai", "domain:cohere.com",
]

if os.path.exists(applied_template):
    with open(applied_template, "r", encoding="utf-8") as f:
        tpl = json.load(f)
else:
    tpl = {
        "api": {"tag": "api", "services": ["HandlerService", "LoggerService", "StatsService", "RoutingService"]},
        "stats": {},
        "policy": {
            "levels": {"0": {"statsUserUplink": True, "statsUserDownlink": True}},
            "system": {
                "statsInboundUplink": True, "statsInboundDownlink": True,
                "statsOutboundUplink": True, "statsOutboundDownlink": True,
            },
        },
        "inbounds": [{"tag": "api", "listen": "127.0.0.1", "port": 62789, "protocol": "dokodemo-door", "settings": {"address": "127.0.0.1"}}],
        "outbounds": [
            {"tag": "direct", "protocol": "freedom", "settings": {"domainStrategy": "UseIPv4"}, "streamSettings": {"sockopt": {"tcpKeepAliveIdle": 20, "tcpKeepAliveInterval": 5, "tcpNoDelay": True}}},
            {"tag": "warp-socks", "protocol": "socks", "settings": {"servers": [{"address": "127.0.0.1", "port": 40000}]}},
            {"tag": "blocked", "protocol": "blackhole", "settings": {"response": {"type": "http"}}},
        ],
        "routing": {
            "domainStrategy": "IPIfNonMatch",
            "rules": [
                {"type": "field", "inboundTag": ["api"], "outboundTag": "api"},
                {"type": "field", "outboundTag": "blocked", "protocol": ["bittorrent"]},
                {"type": "field", "outboundTag": "blocked", "ip": ["geoip:private"]},
                {"type": "field", "outboundTag": "blocked", "domain": ["geosite:category-ads-all"]},
                {"type": "field", "outboundTag": "blocked", "port": "443", "network": "udp", "domain": ai_domains},
                {"type": "field", "outboundTag": "warp-socks", "domain": ai_domains},
                {"type": "field", "outboundTag": "direct", "network": "tcp,udp"},
            ],
        },
        "dns": {"servers": ["1.1.1.1", "8.8.8.8", "1.0.0.1", "localhost"], "queryStrategy": "UseIPv4"},
    }

if not use_native_wg:
    tpl["outbounds"] = [
        o for o in tpl.get("outbounds", [])
        if not (o.get("tag") == "warp-wireguard" and o.get("settings", {}).get("secretKey") == "GENERATE_VIA_WARP_API")
    ]

routing_json = json.dumps(tpl, indent=2)
settings_pairs = [
    ("webListen", "127.0.0.1"),
    ("webPort", "23600"),
    ("webBasePath", "/web_secret_path/"),
    ("subListen", "127.0.0.1"),
    ("subPort", "2095"),
    ("subEnable", "true"),
    ("subPath", "/sub/"),
    ("subURI", f"http://{host_ip}:2096/sub/"),
    ("subJsonPath", "/json_sub/"),
    ("subJsonURI", f"http://{host_ip}:2096/json_sub/"),
    ("subJsonEnable", "true"),
    ("xrayTemplateConfig", routing_json),
]

conn = sqlite3.connect(db_path, timeout=10.0)
try:
    cur = conn.cursor()
    for key, val in settings_pairs:
        cur.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, val),
        )
    conn.commit()
finally:
    conn.close()
PY_SQL_EOF
    echo "✅ 3X-UI panel, subscription server, and hardened Xray routing configured."

    # Start x-ui to load the updated isolated settings and routing template
    systemctl start x-ui || true
    echo "✅ x-ui service started with hardened configuration."
fi

# 13. Deploy Sub-Enhancer background daemon
echo "🛠️ Deploying Sub-Enhancer subscription gateway..."
TARGET_ENHANCER="/usr/local/bin/sub-enhancer.py"

# Note: Sub-Enhancer runs in plain HTTP mode by default on raw VPS IP addresses.
# For TLS subscription distribution, administrators must supply a valid CA-signed certificate
# (e.g., via Let's Encrypt at /etc/x-ui/sub_cert.pem and /etc/x-ui/sub_key.pem)
# and enable SUB_ENABLE_TLS=true. Self-signed certificates cause SSL errors in mobile clients.

if [ -f "$SCRIPT_DIR/sub-enhancer.py" ]; then
    cp "$SCRIPT_DIR/sub-enhancer.py" "$TARGET_ENHANCER"
else
    cat << 'EOF' > "$TARGET_ENHANCER"
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
EOF
fi
chmod +x "$TARGET_ENHANCER"

if [ "$SINGLE_PORT_443" = true ]; then
    SUB_ACTUAL_LISTEN="127.0.0.1"
    SUB_SINGLE_PORT_FLAG="true"
    if [ "$SUB_PORTS" = "2096,28443,80" ]; then
        EFFECTIVE_SUB_PORTS="2096"
    else
        EFFECTIVE_SUB_PORTS="$SUB_PORTS"
    fi
    echo "🔒 Deploying Next-Gen Nginx Stream SNI Multiplexer on port 443..."
    mkdir -p /etc/nginx/stream.d
    if ! grep -q "stream.d" /etc/nginx/nginx.conf 2>/dev/null; then
        cat << 'NGINX_STREAM_EOF' >> /etc/nginx/nginx.conf

stream {
    include /etc/nginx/stream.d/*.conf;
}
NGINX_STREAM_EOF
    fi

    cat << 'NGINX_CONF_EOF' > /etc/nginx/stream.d/sni_multiplexer.conf
map $ssl_preread_server_name $sni_backend {
    dl.google.com           127.0.0.1:10443;
    gateway.icloud.com      127.0.0.1:10444;
    default                 127.0.0.1:10443;
}

server {
    listen 443 reuseport;
    proxy_pass $sni_backend;
    ssl_preread on;
}
NGINX_CONF_EOF

    systemctl enable --now nginx || true
    systemctl reload nginx 2>/dev/null || systemctl restart nginx || true
else
    SUB_ACTUAL_LISTEN="0.0.0.0"
    SUB_SINGLE_PORT_FLAG="false"
    EFFECTIVE_SUB_PORTS="$SUB_PORTS"
fi

cat << EOF > /etc/systemd/system/sub-enhancer.service
[Unit]
Description=Subscription Enhancer Service
After=network.target x-ui.service

[Service]
Type=simple
User=root
NoNewPrivileges=true
PrivateTmp=true
Environment="SUB_PORTS=$EFFECTIVE_SUB_PORTS"
Environment="SUB_LISTEN=$SUB_ACTUAL_LISTEN"
Environment="SUB_PUBLIC_IP=${SUB_PUBLIC_IP_VAL:-}"
Environment="SUB_SINGLE_PORT_443=$SUB_SINGLE_PORT_FLAG"
ExecStart=/usr/bin/python3 $TARGET_ENHANCER
Restart=always
RestartSec=3s

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now sub-enhancer

# 13b. Automated Monthly Maintenance Timer (README Section 7.1)
echo "🕒 Installing automated monthly maintenance timer (vps-maintenance.timer)..."
cat << 'MAINT_EOF' > /usr/local/bin/vps-monthly-maintenance.sh
#!/usr/bin/env bash
set -e
echo "=== [$(date)] Starting Scheduled Monthly Maintenance ==="

DEFAULT_GW=$(ip route show default 2>/dev/null | awk '{print $3}' | head -n1)
DEFAULT_DEV=$(ip route show default 2>/dev/null | awk '{print $5}' | head -n1)
if [ -f /etc/x-ui/x-ui.db ] && [ -n "$DEFAULT_GW" ] && [ -n "$DEFAULT_DEV" ]; then
    REALITY_DEST=$(sqlite3 /etc/x-ui/x-ui.db "SELECT stream_settings FROM inbounds WHERE id=1;" 2>/dev/null | grep -o '"dest": *"[^"]*"' | head -n1 | cut -d'"' -f4)
    if [ -n "$REALITY_DEST" ]; then
        DEST_HOST=$(echo "$REALITY_DEST" | cut -d':' -f1)
        DEST_PORT=$(echo "$REALITY_DEST" | cut -d':' -f2)
        [ -z "$DEST_PORT" ] && DEST_PORT=443
        if ! curl -s -I --max-time 3 "https://${DEST_HOST}:${DEST_PORT}" >/dev/null 2>&1; then
            DEST_IPS=$(getent ahosts "$DEST_HOST" 2>/dev/null | awk '{print $1}' | sort -u)
            for d_ip in $DEST_IPS; do
                ip route replace "$d_ip" via "$DEFAULT_GW" dev "$DEFAULT_DEV" 2>/dev/null || true
            done
        fi
    fi
fi

/usr/bin/x-ui update-all-geofiles || true

systemctl stop x-ui || true
sqlite3 /etc/x-ui/x-ui.db "PRAGMA wal_checkpoint(TRUNCATE); VACUUM;" || true
systemctl start x-ui || true

journalctl --vacuum-time=14d --vacuum-size=100M || true

if [ -f /etc/x-ui/warp_wireguard.json ] || sqlite3 /etc/x-ui/x-ui.db "SELECT value FROM settings WHERE key='xrayTemplateConfig';" 2>/dev/null | grep -q '"warp-wireguard"'; then
    echo "[OK] Native WireGuard WARP outbound configured in Xray Core (0 MB daemon mode)."
elif systemctl list-unit-files warp-svc.service 2>/dev/null | grep -q warp-svc && systemctl is-enabled --quiet warp-svc 2>/dev/null; then
    if ! curl -s -x socks5h://127.0.0.1:40000 --max-time 5 https://www.cloudflare.com/cdn-cgi/trace | grep -q "warp=on"; then
        systemctl restart warp-svc || true
        sleep 3
        warp-cli --accept-tos connect || true
    fi
fi

systemctl restart sub-enhancer || true
systemctl is-active --quiet x-ui || systemctl restart x-ui || true
echo "=== [$(date)] Monthly Maintenance Completed Successfully ==="
MAINT_EOF
chmod 755 /usr/local/bin/vps-monthly-maintenance.sh

cat << 'MAINT_SVC_EOF' > /etc/systemd/system/vps-maintenance.service
[Unit]
Description=Automated Monthly VPS Maintenance & Anti-Censorship Sync
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/vps-monthly-maintenance.sh
StandardOutput=journal
StandardError=journal
MAINT_SVC_EOF

cat << 'MAINT_TMR_EOF' > /etc/systemd/system/vps-maintenance.timer
[Unit]
Description=Timer for Automated Monthly VPS Maintenance
Requires=vps-maintenance.service

[Timer]
OnCalendar=*-*-01 04:30:00
Persistent=true

[Install]
WantedBy=timers.target
MAINT_TMR_EOF

systemctl daemon-reload
systemctl enable --now vps-maintenance.timer || true

# 14. Verification and Health Check Audit
echo "=========================================================="
echo "📊 Post-Deployment Diagnostics & Health Check Audit"
echo "=========================================================="

WARP_CHECK="skipped"
if [ "$SKIP_WARP" = false ]; then
    if [ "$WARP_SUCCESS" = true ] && [ "$NATIVE_WARP" = true ]; then
        WARP_CHECK="active (Native WireGuard in Xray Core, 0 MB daemon RAM)"
    elif curl -x socks5h://127.0.0.1:40000 -s --max-time 4 https://cloudflare.com/cdn-cgi/trace 2>/dev/null | grep -q "warp=on"; then
        WARP_CHECK="active (warp-svc SOCKS5, egress healthy)"
    else
        WARP_CHECK="configured / starting"
    fi
fi

XUI_STATUS="inactive"
if systemctl is-active --quiet x-ui; then
    XUI_STATUS="running (active)"
fi

ENHANCER_STATUS="inactive"
if systemctl is-active --quiet sub-enhancer; then
    ENHANCER_STATUS="running (listen: $SUB_ACTUAL_LISTEN:$EFFECTIVE_SUB_PORTS)"
fi

echo "  • Virtualization:       $VIRT_TYPE"
echo "  • Operating System:     $NAME ($VERSION_ID)"
echo "  • 3X-UI Service:        $XUI_STATUS (bound strictly to 127.0.0.1:23600)"
echo "  • Cloudflare WARP:      $WARP_CHECK"
echo "  • Subscription Gateway: $ENHANCER_STATUS"
if [ "$SINGLE_PORT_443" = true ]; then
    echo "  • Single Port 443:      active (Nginx stream SNI preread; auxiliary ports closed)"
else
    echo "  • Single Port 443:      disabled (direct multi-port listener mode)"
fi
if [ "$ENABLE_HYSTERIA" = true ]; then
    echo "  • Hysteria 2 / QUIC:    ready (443/UDP + port hopping 20000-50000/udp active)"
fi
if [ "$STEALTH_ICMP" = true ]; then
    echo "  • ICMP Posture:         active (Silent Blackhole mode, ping dropped)"
else
    echo "  • ICMP Posture:         active (Stack Mimicry mode, echo responses enabled)"
fi
echo "=========================================================="
echo "🎉 Deployment successfully completed!"
echo "   Next Steps:"
echo "   1. Connect to panel via SSH tunnel: client-tools/open_panel_localhost.bat / .sh"
echo "   2. Configure VLESS Reality inbound on port 443 with SNIs matching your dest certificate."
if [ "$SINGLE_PORT_443" = true ]; then
    echo "   3. Fetch subscription securely via https://<DOMAIN>/sub_path on standard port 443."
else
    echo "   3. Fetch subscription securely via public gateway:"
    echo "      • Universal (Port 80 HTTP, Unblocked): http://${HOST_IP}/sub/<token>"
    echo "      • Direct Gateway (Port 2096 HTTP):     http://${HOST_IP}:2096/sub/<token>"
    echo "      • TLS Gateway (Port 2096 HTTPS):       https://<YOUR_DOMAIN>:2096/sub/<token>"
fi
echo "=========================================================="
