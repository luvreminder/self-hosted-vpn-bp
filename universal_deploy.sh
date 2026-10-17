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
CHECK_ONLY=false
KEEP_ICMP=false
SUB_PORTS="${SUB_PORTS:-2096,28443}"

show_help() {
    cat << 'EOF'
Usage: sudo ./universal_deploy.sh [OPTIONS]

Options:
  -h, --help        Show this help message and exit.
  -c, --check       Run environment and hardware compatibility checks without modifying the system.
  --skip-swap       Skip automatic 2 GB swapfile allocation.
  --skip-warp       Skip Cloudflare WARP SOCKS5 client deployment.
  --keep-icmp       Keep standard ICMP echo responses active (Stack Mimicry against ML/behavioral DPI).
  --sub-ports PORTS Custom comma-separated subscription gateway ports (default: 2096,28443).

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
        --keep-icmp)
            KEEP_ICMP=true
            shift
            ;;
        --sub-ports)
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
        # Install iptables persistence utility non-interactively
        echo iptables-persistent iptables-persistent/autosave_v4 boolean true | debconf-set-selections || true
        echo iptables-persistent iptables-persistent/autosave_v6 boolean true | debconf-set-selections || true
        apt install -y iptables-persistent || true
        ;;
    rocky|almalinux|rhel|centos)
        dnf install -y epel-release || true
        dnf install -y curl wget git jq sqlite iptables iptables-services python3 python3-pip ca-certificates
        systemctl enable --now iptables || true
        ;;
esac

# 7. Kernel performance tuning (TCP BBR + Optional ICMP Blackhole)
echo "⚡ Configuring kernel: Enabling TCP BBR congestion control..."
sed -i '/net.core.default_qdisc/d' /etc/sysctl.conf
sed -i '/net.ipv4.tcp_congestion_control/d' /etc/sysctl.conf
sed -i '/net.ipv4.icmp_echo_ignore_all/d' /etc/sysctl.conf

echo "net.core.default_qdisc=fq" >> /etc/sysctl.conf
echo "net.ipv4.tcp_congestion_control=bbr" >> /etc/sysctl.conf
if [ "$KEEP_ICMP" = false ]; then
    echo "net.ipv4.icmp_echo_ignore_all=1" >> /etc/sysctl.conf
else
    echo "net.ipv4.icmp_echo_ignore_all=0" >> /etc/sysctl.conf
fi
sysctl -p

# 8. Host protection against BitTorrent (Layer-7 Anti-DMCA)
# Note: Xray proxy traffic is filtered inside Xray Core via "protocol": ["bittorrent"] -> blackhole.
# The following iptables rules provide idempotent kernel defense-in-depth for host processes.
echo "🛡️ Deploying Layer-7 BitTorrent packet filters (Host & Forwarding)..."
for chain in OUTPUT FORWARD; do
    for proto in tcp udp; do
        for str in "BitTorrent" "BitTorrent protocol"; do
            iptables -C "$chain" -p "$proto" -m string --string "$str" --algo bm -j DROP 2>/dev/null || \
            iptables -I "$chain" -p "$proto" -m string --string "$str" --algo bm -j DROP || true
        done
    done
done

# Persist iptables rules across reboots
if [ "$OS_ID" = "rocky" ] || [ "$OS_ID" = "almalinux" ] || [ "$OS_ID" = "rhel" ]; then
    service iptables save || true
elif [ "$OS_ID" = "ubuntu" ] || [ "$OS_ID" = "debian" ]; then
    netfilter-persistent save || true
fi

# 9. Firewall rules configuration (firewalld / ufw) - Strict Default Deny
echo "🔒 Configuring firewall: Enforcing default-deny with SSH (22/tcp) & VLESS Reality (443/tcp)..."
case "$OS_ID" in
    ubuntu|debian)
        ufw default deny incoming || true
        ufw default allow outgoing || true
        ufw allow 22/tcp comment 'SSH' || true
        ufw allow 443/tcp comment 'VLESS-REALITY' || true
        # 3X-UI Web (23600) and Sub (2095) remain closed to public internet
        ufw --force enable || true
        echo "✅ UFW configured and activated."
        ;;
    rocky|almalinux|rhel|centos)
        systemctl enable --now firewalld || true
        firewall-cmd --permanent --remove-service=cockpit 2>/dev/null || true
        firewall-cmd --permanent --add-service=ssh || true
        firewall-cmd --permanent --add-port=443/tcp || true
        # 3X-UI Web (23600) and Sub (2095) remain closed to public internet
        firewall-cmd --reload || true
        echo "✅ Firewalld configured and activated."
        ;;
esac

# 10. Deploy Cloudflare WARP SOCKS5 client (Port 40000)
if [ "$SKIP_WARP" = false ]; then
    echo "🌐 Deploying Cloudflare WARP in local SOCKS5 proxy mode..."
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
    else
        echo "⚠️ Warning: WARP socket took longer to start. You can run 'warp-cli connect' manually."
    fi
fi

# 11. Deploy 3X-UI management panel
echo "🎛️ Deploying 3X-UI management panel..."
if [ ! -d "/usr/local/x-ui" ]; then
    bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh)
fi

# 12. Enforce strict localhost isolation & apply hardened Xray routing template
DB_PATH="/etc/x-ui/x-ui.db"
TEMPLATE_FILE="$SCRIPT_DIR/xray_template_config.json"

# Stop x-ui to safely update database settings and prevent race conditions
systemctl stop x-ui || true

if [ -f "$DB_PATH" ]; then
    echo "🔒 Hardening 3X-UI panel: Binding strictly to 127.0.0.1:23600 (accessible only via SSH tunnel)..."
    sqlite3 "$DB_PATH" << SQL_EOF
INSERT INTO settings (key, value) VALUES ('webListen', '127.0.0.1')
ON CONFLICT(key) DO UPDATE SET value=excluded.value;

INSERT INTO settings (key, value) VALUES ('webPort', '23600')
ON CONFLICT(key) DO UPDATE SET value=excluded.value;

INSERT INTO settings (key, value) VALUES ('webBasePath', '/web_secret_path/')
ON CONFLICT(key) DO UPDATE SET value=excluded.value;

INSERT INTO settings (key, value) VALUES ('subListen', '127.0.0.1')
ON CONFLICT(key) DO UPDATE SET value=excluded.value;

INSERT INTO settings (key, value) VALUES ('subPort', '2095')
ON CONFLICT(key) DO UPDATE SET value=excluded.value;

INSERT INTO settings (key, value) VALUES ('subEnable', 'true')
ON CONFLICT(key) DO UPDATE SET value=excluded.value;

INSERT INTO settings (key, value) VALUES ('subPath', '/sub/')
ON CONFLICT(key) DO UPDATE SET value=excluded.value;
SQL_EOF
    echo "✅ 3X-UI panel and subscription server bound strictly to localhost."

    echo "⚙️ Configuring hardened Xray Core split-routing in 3X-UI database..."
    if [ -f "$TEMPLATE_FILE" ]; then
        ROUTING_JSON=$(cat "$TEMPLATE_FILE")
    else
        # Embedded fallback routing template (Full with api, stats, dokodemo-door, bittorrent, and AI QUIC block)
        ROUTING_JSON='{"api":{"tag":"api","services":["HandlerService","LoggerService","StatsService","RoutingService"]},"stats":{},"policy":{"levels":{"0":{"statsUserUplink":true,"statsUserDownlink":true}},"system":{"statsInboundUplink":true,"statsInboundDownlink":true,"statsOutboundUplink":true,"statsOutboundDownlink":true}},"inbounds":[{"tag":"api","listen":"127.0.0.1","port":62789,"protocol":"dokodemo-door","settings":{"address":"127.0.0.1"}}],"outbounds":[{"tag":"direct","protocol":"freedom","settings":{"domainStrategy":"UseIPv4"}},{"tag":"warp-socks","protocol":"socks","settings":{"servers":[{"address":"127.0.0.1","port":40000}]}},{"tag":"blocked","protocol":"blackhole","settings":{"response":{"type":"http"}}}],"routing":{"domainStrategy":"IPIfNonMatch","rules":[{"type":"field","inboundTag":["api"],"outboundTag":"api"},{"type":"field","outboundTag":"blocked","protocol":["bittorrent"]},{"type":"field","outboundTag":"blocked","ip":["geoip:private"]},{"type":"field","outboundTag":"blocked","domain":["geosite:category-ads-all"]},{"type":"field","outboundTag":"blocked","port":"443","network":"udp","domain":["geosite:openai","geosite:anthropic","geosite:google-gemini","geosite:perplexity","domain:openai.com","domain:chatgpt.com","domain:anthropic.com","domain:claude.ai","domain:gemini.google.com","domain:aistudio.google.com","domain:perplexity.ai"]},{"type":"field","outboundTag":"warp-socks","domain":["geosite:openai","geosite:anthropic","geosite:google-gemini","geosite:perplexity","domain:openai.com","domain:chatgpt.com","domain:oaistatic.com","domain:oaiusercontent.com","domain:sora.com","domain:ai.com","domain:chat.openai.com","domain:auth0.openai.com","domain:client-api.arkoselabs.com","domain:featuregates.org","domain:statsig.com","domain:statsigapi.net","domain:anthropic.com","domain:claude.ai","domain:claude.com","domain:gemini.google.com","domain:aistudio.google.com","domain:generativelanguage.googleapis.com","domain:alkalimakersuite-pa.googleapis.com","domain:proactivebackend-pa.googleapis.com","domain:deepmind.google","domain:notebooklm.google","domain:notebooklm.google.com","domain:ai.google.dev","domain:generativeai.google","domain:vertexai.googleapis.com","domain:aiplatform.googleapis.com","domain:cursor.sh","domain:cursor.com","domain:cursor-cdn.com","domain:copilot.microsoft.com","domain:perplexity.ai","domain:midjourney.com","domain:x.ai","domain:grok.com","domain:deepseek.com","domain:mistral.ai","domain:cohere.com"]},{"type":"field","outboundTag":"direct","network":"tcp,udp"}]},"dns":{"servers":["https://1.1.1.1/dns-query","https://8.8.8.8/dns-query","1.1.1.1","8.8.8.8","localhost"],"queryStrategy":"UseIPv4"}}'
    fi

    # Update or insert xrayTemplateConfig in SQLite settings table
    sqlite3 "$DB_PATH" << SQL_EOF
INSERT INTO settings (key, value) VALUES ('xrayTemplateConfig', '$ROUTING_JSON')
ON CONFLICT(key) DO UPDATE SET value=excluded.value;
SQL_EOF

    # Start x-ui to load the updated isolated settings and routing template
    systemctl start x-ui || true
    echo "✅ Hardened Xray routing applied and x-ui service restarted."
fi

# 13. Deploy Sub-Enhancer background daemon
echo "🛠️ Deploying Sub-Enhancer subscription gateway..."
TARGET_ENHANCER="/usr/local/bin/sub-enhancer.py"

# Generate local self-signed TLS cert for subscription encryption if not present
if [ ! -f "/etc/x-ui/sub_cert.pem" ]; then
    mkdir -p /etc/x-ui
    openssl req -x509 -newkey rsa:2048 -nodes -keyout /etc/x-ui/sub_key.pem -out /etc/x-ui/sub_cert.pem -days 3650 -subj "/CN=SecureSub" 2>/dev/null || true
    chmod 600 /etc/x-ui/sub_key.pem 2>/dev/null || true
fi

if [ -f "$SCRIPT_DIR/sub-enhancer.py" ]; then
    cp "$SCRIPT_DIR/sub-enhancer.py" "$TARGET_ENHANCER"
else
    cat << 'EOF' > "$TARGET_ENHANCER"
#!/usr/bin/env python3
import sys, os, re, ssl, sqlite3, base64, urllib.request, urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

UPSTREAM = os.environ.get("SUB_UPSTREAM", "http://127.0.0.1:2095")
DB_PATH = os.environ.get("XUI_DB_PATH", "/etc/x-ui/x-ui.db")
SUB_LISTEN = os.environ.get("SUB_LISTEN", "127.0.0.1")
SSL_CERT = os.environ.get("SUB_SSL_CERT", "/etc/x-ui/sub_cert.pem")
SSL_KEY = os.environ.get("SUB_SSL_KEY", "/etc/x-ui/sub_key.pem")

def get_sni_remarks():
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
            msg = f"Bad Gateway: {e}".encode("utf-8")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            if method == "GET":
                self.wfile.write(msg)
            return

        if status == 200 and method == "GET" and body:
            try:
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
    server.serve_forever()

if __name__ == "__main__":
    import threading
    ssl_context = None
    if os.path.exists(SSL_CERT) and os.path.exists(SSL_KEY):
        try:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(certfile=SSL_CERT, keyfile=SSL_KEY)
            ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
        except Exception:
            ssl_context = None

    raw_ports = os.environ.get("SUB_PORTS", "2096,28443").split(",")
    ports = [int(p.strip()) for p in raw_ports if p.strip()]
    for p in ports[:-1]:
        t = threading.Thread(target=start_server, args=(SUB_LISTEN, p, ssl_context), daemon=True)
        t.start()
    start_server(SUB_LISTEN, ports[-1], ssl_context)
EOF
fi
chmod +x "$TARGET_ENHANCER"

cat << EOF > /etc/systemd/system/sub-enhancer.service
[Unit]
Description=Subscription Enhancer Service
After=network.target x-ui.service

[Service]
Type=simple
User=root
Environment="SUB_PORTS=$SUB_PORTS"
Environment="SUB_LISTEN=127.0.0.1"
ExecStart=/usr/bin/python3 $TARGET_ENHANCER
Restart=always
RestartSec=3s

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now sub-enhancer

# 14. Verification and Health Check Audit
echo "=========================================================="
echo "📊 Post-Deployment Diagnostics & Health Check Audit"
echo "=========================================================="

WARP_CHECK="skipped"
if [ "$SKIP_WARP" = false ]; then
    if curl -x socks5h://127.0.0.1:40000 -s --max-time 4 https://cloudflare.com/cdn-cgi/trace | grep -q "warp=on"; then
        WARP_CHECK="active (warp=on, egress healthy)"
    else
        WARP_CHECK="starting / connecting"
    fi
fi

XUI_STATUS="inactive"
if systemctl is-active --quiet x-ui; then
    XUI_STATUS="running (active)"
fi

ENHANCER_STATUS="inactive"
if systemctl is-active --quiet sub-enhancer; then
    ENHANCER_STATUS="running (ports: $SUB_PORTS)"
fi

echo "  • Virtualization:       $VIRT_TYPE"
echo "  • Operating System:     $NAME ($VERSION_ID)"
echo "  • 3X-UI Service:        $XUI_STATUS (bound strictly to 127.0.0.1:23600)"
echo "  • Cloudflare WARP SOCKS:$WARP_CHECK"
echo "  • Subscription Gateway: $ENHANCER_STATUS (isolated on 127.0.0.1)"
if [ "$KEEP_ICMP" = true ]; then
    echo "  • ICMP Posture:         active (Stack Mimicry mode, echo responses enabled)"
else
    echo "  • ICMP Posture:         active (Silent Blackhole mode, ping dropped)"
fi
echo "=========================================================="
echo "🎉 Deployment successfully completed!"
echo "   Next Steps:"
echo "   1. Connect to panel via SSH tunnel: client-tools/open_panel_localhost.bat / .sh"
echo "   2. Configure VLESS Reality inbound on port 443 with SNIs matching your dest certificate."
echo "   3. Fetch subscription securely over SSH tunnel (http://127.0.0.1:23600/ or :2096/)."
echo "=========================================================="
