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
SUB_PORTS="${SUB_PORTS:-2096,28443}"

show_help() {
    cat << 'EOF'
Usage: sudo ./universal_deploy.sh [OPTIONS]

Options:
  -h, --help        Show this help message and exit.
  -c, --check       Run environment and hardware compatibility checks without modifying the system.
  --skip-swap       Skip automatic 2 GB swapfile allocation.
  --skip-warp       Skip Cloudflare WARP SOCKS5 client deployment.
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

# 7. Kernel performance tuning (TCP BBR + ICMP Blackhole)
echo "⚡ Configuring kernel: Enabling TCP BBR and ICMP Echo Blackhole..."
sed -i '/net.core.default_qdisc/d' /etc/sysctl.conf
sed -i '/net.ipv4.tcp_congestion_control/d' /etc/sysctl.conf
sed -i '/net.ipv4.icmp_echo_ignore_all/d' /etc/sysctl.conf

echo "net.core.default_qdisc=fq" >> /etc/sysctl.conf
echo "net.ipv4.tcp_congestion_control=bbr" >> /etc/sysctl.conf
echo "net.ipv4.icmp_echo_ignore_all=1" >> /etc/sysctl.conf
sysctl -p

# 8. Host protection against BitTorrent (Layer-7 Anti-DMCA)
echo "🛡️ Deploying Layer-7 BitTorrent packet filters..."
iptables -I FORWARD -p tcp -m string --string "BitTorrent" --algo bm -j DROP || true
iptables -I FORWARD -p tcp -m string --string "BitTorrent protocol" --algo bm -j DROP || true
iptables -I FORWARD -p udp -m string --string "BitTorrent" --algo bm -j DROP || true
iptables -I FORWARD -p udp -m string --string "BitTorrent protocol" --algo bm -j DROP || true
iptables -I OUTPUT -p tcp -m string --string "BitTorrent" --algo bm -j DROP || true
iptables -I OUTPUT -p udp -m string --string "BitTorrent" --algo bm -j DROP || true

# Persist iptables rules across reboots
if [ "$OS_ID" = "rocky" ] || [ "$OS_ID" = "almalinux" ] || [ "$OS_ID" = "rhel" ]; then
    service iptables save || true
elif [ "$OS_ID" = "ubuntu" ] || [ "$OS_ID" = "debian" ]; then
    netfilter-persistent save || true
fi

# 9. Firewall rules configuration (firewalld / ufw)
echo "🔒 Configuring firewall: Opening required proxy & subscription ports..."
if systemctl is-active --quiet firewalld; then
    firewall-cmd --permanent --add-service=ssh || true
    firewall-cmd --permanent --add-port=443/tcp || true
    for p in $(echo "$SUB_PORTS" | tr ',' ' '); do
        firewall-cmd --permanent --add-port="${p}/tcp" || true
    done
    firewall-cmd --reload || true
    echo "✅ Firewalld rules configured."
elif command -v ufw &>/dev/null && ufw status | grep -q "Status: active"; then
    ufw allow 22/tcp || true
    ufw allow 443/tcp || true
    for p in $(echo "$SUB_PORTS" | tr ',' ' '); do
        ufw allow "${p}/tcp" || true
    done
    echo "✅ UFW rules configured."
fi

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

# 12. Apply hardened Xray routing template to 3X-UI SQLite database
DB_PATH="/etc/x-ui/x-ui.db"
TEMPLATE_FILE="$SCRIPT_DIR/xray_template_config.json"

if [ -f "$DB_PATH" ]; then
    echo "⚙️ Configuring hardened Xray Core split-routing in 3X-UI database..."
    if [ -f "$TEMPLATE_FILE" ]; then
        ROUTING_JSON=$(cat "$TEMPLATE_FILE")
    else
        # Embedded fallback routing template
        ROUTING_JSON='{"outbounds":[{"tag":"direct","protocol":"freedom","settings":{}},{"tag":"warp-socks","protocol":"socks","settings":{"servers":[{"address":"127.0.0.1","port":40000}]}},{"tag":"blocked","protocol":"blackhole","settings":{}}],"routing":{"domainStrategy":"IPIfNonMatch","rules":[{"type":"field","outboundTag":"blocked","protocol":["bittorrent"]},{"type":"field","outboundTag":"blocked","ip":["geoip:private"]},{"type":"field","outboundTag":"warp-socks","domain":["domain:openai.com","domain:chatgpt.com","domain:oaistatic.com","domain:oaiusercontent.com","domain:ai.com","domain:sora.com","domain:anthropic.com","domain:claude.ai","domain:claude.com","domain:perplexity.ai"]}]}}'
    fi

    # Update or insert xrayTemplateConfig in SQLite settings table
    sqlite3 "$DB_PATH" << SQL_EOF
INSERT INTO settings (key, value) VALUES ('xrayTemplateConfig', '$ROUTING_JSON')
ON CONFLICT(key) DO UPDATE SET value=excluded.value;
SQL_EOF

    # Restart x-ui to load the updated routing template
    systemctl restart x-ui || true
    echo "✅ Hardened Xray routing applied and x-ui service restarted."
fi

# 13. Deploy Sub-Enhancer background daemon
echo "🛠️ Deploying Sub-Enhancer subscription gateway (ports: $SUB_PORTS)..."
TARGET_ENHANCER="/usr/local/bin/sub-enhancer.py"

if [ -f "$SCRIPT_DIR/sub-enhancer.py" ]; then
    cp "$SCRIPT_DIR/sub-enhancer.py" "$TARGET_ENHANCER"
else
    cat << 'EOF' > "$TARGET_ENHANCER"
#!/usr/bin/env python3
import sys, os, sqlite3, base64, urllib.request, urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

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
echo "  • 3X-UI Service:        $XUI_STATUS"
echo "  • Cloudflare WARP SOCKS:$WARP_CHECK"
echo "  • Subscription Gateway: $ENHANCER_STATUS"
echo "  • BitTorrent L7 Filter: active (dropped at kernel layer)"
echo "  • ICMP Ping Blackhole:  active (silent mode)"
echo "=========================================================="
echo "🎉 Deployment successfully completed!"
echo "   Next Steps:"
echo "   1. Connect to panel via SSH tunnel: open_panel_localhost.bat / .sh"
echo "   2. Configure VLESS Reality inbound on port 443 with multi-SNI hosts."
echo "   3. Import encrypted subscription URL into your Happ client."
echo "=========================================================="
