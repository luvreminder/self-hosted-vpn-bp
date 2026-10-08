# 🌐 Golden Standard Self-Hosted VPN Blueprint & Deployment Guide

> **Production-grade reference architecture for resilient, high-performance personal proxy infrastructure.**  
> `VLESS-Reality` • `XTLS-Vision` • `3X-UI` • `Cloudflare WARP SOCKS5` • `Happ Multi-SNI` • `Sub-Enhancer`

> [!IMPORTANT]
> **Educational & Informational Disclaimer**  
> This documentation and all associated configuration materials are provided strictly for informational, educational, and evaluation purposes and cannot cover every potential edge case or problematic scenario. System operators are strongly advised to analyze this information specifically for their individual use case, evaluate risks independently, and thoroughly verify operation within their own technical environment and unique operational circumstances.

**Target Audience:** Systems Administrators, DevOps Engineers, Infrastructure Architects, and Autonomous AI Coding Agents (*Antigravity, Cursor, Claude Code, ChatGPT*).

---

## 📖 Overview, Purpose & Repository Contents

### Why This Blueprint Exists
Deploying a secure, censorship-resistant personal proxy or VPN infrastructure using modern protocols (VLESS Reality, XTLS-Vision, and management panels like 3X-UI) is routinely undermined by fragmented, outdated, and fundamentally insecure tutorials online. Most public guides suffer from severe real-world shortcomings:

1. **Severe Security Exposures:** Most instructions advise opening the web panel port (`2053`, `2096`) directly to the public internet with default credentials. Within minutes, automated scanners (Shodan, Censys) index the server, launching automated credential stuffing attacks and making the server an obvious target for hosting provider scrutiny.
2. **Datacenter IP Blocks on AI Services:** Public VPS IP addresses from commercial cloud datacenters are heavily rate-limited or outright blocked by AI service providers (OpenAI ChatGPT, Anthropic Claude, Google Gemini, Perplexity) with persistent Cloudflare Turnstile captchas or "Access Denied" errors.
3. **Throughput Degradation via Blanket WARP:** Naive tutorials route all VPS traffic through Cloudflare WARP, throttling gigabit bandwidth down to 5–15 Mbps and adding unnecessary packet latency.
4. **Host Account Suspension Risk (BitTorrent):** Standard setups do not restrict peer-to-peer file sharing at the server level. Unintentional BitTorrent traffic triggers DMCA copyright infringement notices, leading to immediate VPS suspension by commercial hosting providers.
5. **Subscription Display Bugs in Client Apps:** Modern panels like 3X-UI assign identical remark titles to multiple domain endpoints (Hosts) under the same inbound. Clients like Happ cannot distinguish between cellular and Wi-Fi profiles, and minor URL typos result in confusing HTTP 404 errors.
6. **Fragile Operating System Assumptions:** Community scripts written strictly for single Ubuntu versions break unpredictably on enterprise Linux distributions due to differences in SELinux, firewalls, and package managers.
7. **Vulnerability to Active Probing & Network Scanners:** Standard guides ignore ICMP ping exposure and censorship active probing mechanisms (such as state-level deep packet inspection crawlers and middlebox probes). When censors or bot scanners probe an unknown proxy IP, misconfigured setups leak default certificates, reset connections abnormally, or use poorly selected SNIs that trigger IP-ASN discrepancy alerts.

### How This Blueprint Helps
This specification represents a complete, hardened **Golden Standard reference architecture** that resolves each of these vulnerabilities:

* **Production-Grade Isolation:** The 3X-UI panel is bound strictly to `localhost` and accessible only through an encrypted SSH tunnel. The server operates in an ICMP blackhole mode (ignoring ping probes).
* **Intelligent Outbound Split-Routing:** High-performance direct egress for streaming, gaming, and general web browsing, combined with transparent, selective routing through a local Cloudflare WARP SOCKS5 proxy (`127.0.0.1:40000`) exclusively for AI platforms.
* **Multi-SNI Disguise Profiles:** Independent server masquerades tailored for cellular networks (`gateway.icloud.com`) and broadband Wi-Fi (`dl.google.com`).
* **Automated Subscription Gateway (`sub-enhancer`):** An autonomous background daemon that resolves dynamic node labels from SQLite, normalizes URL input errors, and serves encrypted subscriptions (`happ://crypt5/...`) with automatic 12-hour background refresh headers.
* **Kernel-Level Abuse Protection:** Layer-7 packet filtering drops BitTorrent handshake strings before packets leave the server.
* **Universal Compatibility:** Fully tested across modern enterprise Linux (Rocky Linux 9, AlmaLinux 9) and Debian-family releases (Ubuntu 22.04/24.04, Debian 12).
* **Active Probing Defense & Comprehensive Stealth:** Full ICMP blackhole mode (ignoring ping sweeps) coupled with VLESS Reality cryptographic fallback to genuine Apple and Google TLS 1.3 endpoints. Unauthenticated probes receive authentic third-party SSL certificates, while uTLS and XTLS-Vision neutralize heuristic DPI fingerprinting.

### 📦 Repository & Community Edition Contents
This repository distribution bundle includes:
* **`README.md`**: Complete architectural reference, deployment blueprint, and operational runbook.
* **`universal_deploy.sh`**: Single-command, idempotent bash installer supporting automated deployment.
* **`sub-enhancer.py`**: Standalone Python HTTP subscription gateway and URL transformer.
* **`xray_template_config.json`**: Hardened Xray core routing configuration with AI split-routing.
* **`credentials.example.txt`**: Sanitized credentials template for local administration.
* **`client-tools/`**: Cross-platform client connection and administration scripts (`open_panel_localhost.bat`, `open_panel_localhost.sh`, `change_password.bat`, `change_password.sh`).
* **`.gitignore` & `.gitattributes`**: Git repository sanitation rules and cross-platform line ending normalization.
* **`LICENSE`**: Open-source MIT License.

---

## 📑 Table of Contents

* [🚀 Quick Start Deployment](#-quick-start-deployment)
* [📋 1. VPS System & Hardware Requirements](#-1-vps-system--hardware-requirements)
  * [1.1. Hardware Specifications](#11-hardware-specifications)
  * [1.2. Virtualization Platform](#12-virtualization-platform)
* [🐧 2. Operating System Compatibility Matrix](#-2-operating-system-compatibility-matrix)
  * [2.1. Supported Operating Systems](#21-supported-operating-systems)
  * [2.2. Incompatible & Deprecated Operating Systems](#22-incompatible--deprecated-operating-systems-do-not-use)
* [🧭 3. Architectural Design Rationale](#-3-architectural-design-rationale)
  * [3.1. Deep Analysis: Scanner Detection, Active Probing & Censorship Resistance](#31-deep-analysis-scanner-detection-active-probing--censorship-resistance)
  * [3.2. Advanced Anti-Fingerprinting & Evasion Hardening](#32-advanced-anti-fingerprinting--evasion-hardening)
* [🛠️ 4. Step-by-Step Deployment Procedure](#️-4-step-by-step-deployment-procedure)
  * [Step 0: Swap Allocation](#step-0-swap-allocation-crucial-for-1-gb-ram-nodes)
  * [Step 1: Kernel Performance & Stealth](#step-1-kernel-performance--stealth-configuration)
  * [Step 2: Layer-7 BitTorrent Filtering](#step-2-layer-7-bittorrent-filtering-anti-dmca)
  * [Step 3: Deploy Cloudflare WARP SOCKS5](#step-3-deploy-cloudflare-warp-socks5-gateway)
  * [Step 4: Install 3X-UI & Isolate Panel Access](#step-4-install-3x-ui--isolate-panel-access)
  * [Step 5: Configure Xray Core Routing](#step-5-configure-xray-core-routing-xraytemplateconfig)
  * [Step 6: Configure VLESS Reality & Multi-SNI Endpoints](#step-6-configure-vless-reality--multi-sni-endpoints)
  * [Step 7: Deploy Subscription Gateway](#step-7-deploy-subscription-gateway-sub-enhancer)
* [📱 5. Client Application Setup & Multi-SNI Profiles](#-5-client-application-setup--multi-sni-profiles)
  * [5.1. Importing the Encrypted Subscription](#51-importing-the-encrypted-subscription-happ--shadowrocket--v2rayn)
  * [5.2. Client-Side Split Tunneling & Routing Policies](#52-client-side-split-tunneling--routing-policies)
  * [5.3. Essential Client DNS & Anti-Loop Configuration](#53-essential-client-dns--anti-loop-configuration)
  * [5.4. Administration Helper Scripts](#54-administration-helper-scripts-client-tools)
* [🔧 6. Maintenance, Operations & Troubleshooting Runbook](#-6-maintenance-operations--troubleshooting-runbook)
  * [6.1. Regular Security Maintenance](#61-regular-security-maintenance)
  * [6.2. Log Maintenance & Disk Sanitation](#62-log-maintenance--disk-sanitation)
  * [6.3. Service Healthcheck Procedures](#63-service-healthcheck-procedures)
  * [6.4. Database Backup Strategy](#64-database-backup-strategy)
  * [6.5. Troubleshooting Runbook](#65-troubleshooting-runbook)
  * [6.6. Verification of Server Stealth & Scanner Invisibility](#66-verification-of-server-stealth--scanner-invisibility-audit-runbook)
* [📄 License](#-license)
* [⚠️ Educational Disclaimer & Operational Liability Notice](#️-educational-disclaimer--operational-liability-notice)

---

## 🚀 Quick Start Deployment

### Automated One-Line Deployment
Supported Operating Systems: **Rocky Linux 9**, **AlmaLinux 9**, **Ubuntu 22.04 / 24.04 LTS**, **Debian 12 (Bookworm)**.  
*Virtualization Requirement:* **KVM**, **VMware ESXi**, or **Bare-metal** (OpenVZ and LXC are not supported).

Connect to your clean VPS instance via SSH and run:
```bash
# Upload or clone repository on your server and execute:
chmod +x universal_deploy.sh
sudo ./universal_deploy.sh

# Optional Flags:
# sudo ./universal_deploy.sh --check            # Dry-run environment compatibility check
# sudo ./universal_deploy.sh --skip-swap        # Skip swapfile allocation
# sudo ./universal_deploy.sh --skip-warp        # Skip Cloudflare WARP client setup
# sudo ./universal_deploy.sh --sub-ports 28443  # Custom subscription gateway ports
```
*The installer automatically validates hypervisor capabilities, configures a 2 GB swap if RAM ≤ 1.5 GB, activates TCP BBR with ICMP ping blackholing, sets up Layer-7 BitTorrent packet filtering with reboot persistence, registers Cloudflare WARP SOCKS5 on port 40000, deploys 3X-UI, injects hardened Xray split-routing into SQLite, and starts the dual-port Sub-Enhancer background service.*

---

## 📋 1. VPS System & Hardware Requirements

To guarantee optimal performance, low latency, and zero out-of-memory (OOM) incidents, the hosting instance must satisfy the following hardware and platform criteria:

### 1.1. Hardware Specifications

| Resource | Minimum Requirement | Recommended Specification | Technical Rationale |
| :--- | :--- | :--- | :--- |
| **CPU Architecture** | `x86_64` (AMD64) | `x86_64` with `AES-NI` support | Hardware AES acceleration minimizes CPU overhead during TLS/Vision crypto handshakes. |
| **Processor (vCPU)** | 1 vCPU (at least 2.0 GHz) | 2 vCPU (modern AMD EPYC / Intel Xeon) | 1 core easily handles personal use; 2 cores guarantee full 1 Gbps+ throughput during concurrent multi-device transfers. |
| **RAM** | 1 GB RAM | 2 GB RAM (or 1 GB RAM + 1–2 GB Swap) | Base footprint: Linux kernel (~150 MB), Xray-core (~60 MB), WARP daemon (~100 MB), 3X-UI (~50 MB), Sub-Enhancer (~15 MB) = ~375 MB total. Swap is required on 1 GB nodes to prevent OOM termination. |
| **Storage** | 10 GB SSD / NVMe | 20+ GB NVMe SSD | Rapid I/O is critical for SQLite database transactions, `journalctl` logging, and kernel upgrades. |
| **Network Interface** | 100 Mbps (1 IPv4) | 1 Gbps (Dedicated Static Public IPv4) | Direct public IPv4 address required. NAT/shared IP environments are not supported. |

### 1.2. Virtualization Platform

* **Supported:** **KVM** (Kernel-based Virtual Machine), **VMware ESXi**, **Xen HVM**, **Bare-metal Dedicated Servers**.  
  *Rationale:* Requires full administrative access to Linux kernel sysctl parameters (`/etc/sysctl.conf`), capability to load the TCP BBR congestion control module, creation of virtual network `tun` adapters for Cloudflare WARP, and `iptables string` matching.
* **NOT Supported:** ❌ **OpenVZ**, ❌ **LXC**.  
  *Rationale:* Container-based virtualization shares the host kernel. OpenVZ prevents TCP BBR activation, and the Cloudflare WARP daemon fails with critical errors due to lack of direct `/dev/net/tun` device control.

---

## 🐧 2. Operating System Compatibility Matrix

This architecture relies on modern systemd, Python 3.9+, and recent Cloudflare WARP client builds.

### 2.1. Supported Operating Systems

1. **Rocky Linux 9 (Recommended for Enterprise Stability):**
   * **Kernel:** Linux 5.14+ (native TCP BBR v3, eBPF, nftables).
   * **Base Stack:** Python 3.9+, systemd 252+, modern glibc 2.34+.
   * **Characteristics:** Long-term enterprise stability, 1:1 binary compatibility with Red Hat Enterprise Linux 9, official Cloudflare WARP RPM package support.
2. **AlmaLinux 9:**
   * Full 1:1 equivalent to Rocky Linux 9 on RHEL 9 codebase.
3. **Ubuntu 22.04 LTS / Ubuntu 24.04 LTS:**
   * **Kernel:** Linux 5.15+ (22.04) / Linux 6.8+ (24.04).
   * **Characteristics:** Extensive documentation, rapid package installation via `apt`, official Cloudflare APT repository support.
4. **Debian 12 (Bookworm):**
   * **Kernel:** Linux 6.1+.
   * **Characteristics:** Minimalist, lightweight base footprint. Requires initial installation of `curl`, `sudo`, and `iptables`.

### 2.2. Incompatible & Deprecated Operating Systems (Do Not Use)

* ❌ **Rocky Linux 8 / AlmaLinux 8 / CentOS 7/8 / RHEL 8:**
  *Deprecated stack.* The default 4.18 kernel lacks modern networking features. The official Cloudflare WARP client for RHEL 8 suffers from unresolved glibc/OpenSSL shared library dependency conflicts, causing `warp-svc` startup crashes.
* ❌ **Debian 10 / Ubuntu 20.04:**
  *End of mainstream lifecycle.* Outdated compiler toolchains and networking utilities.

---

## 🧭 3. Architectural Design Rationale

This deployment model addresses common operational challenges:

1. **VLESS-REALITY + XTLS-Vision (Port 443):**
   Eliminates protocol signatures characteristic of legacy VPNs (WireGuard, OpenVPN, Shadowsocks). To external deep packet inspection (DPI) firewalls, connections are mathematically indistinguishable from regular TLS 1.3 traffic to authentic third-party servers.
2. **Multi-SNI Disguise Framework:**
   * **Mobile Stealth (`gateway.icloud.com`):** Apple iCloud Private Relay infrastructure cannot be indiscriminately blocked by mobile operators without breaking synchronization for millions of consumer iOS and macOS devices.
   * **Fast Wi-Fi (`dl.google.com`):** Google CDN possesses high-capacity global direct peering, delivering maximum line-rate download speeds and ultra-low latency for residential broadband connections.
3. **Intelligent Multi-Egress Routing Architecture:**
   * **Selective Proxy Egress (WARP SOCKS5 on `127.0.0.1:40000`):** Target services that aggressively restrict commercial datacenter ASNs (e.g. OpenAI, Anthropic, Perplexity) are routed through Cloudflare edge IP space, bypassing commercial hosting blocks and recurring CAPTCHAs.
   * **Direct Native Egress (`direct`):** General web traffic, high-throughput media, and services sensitive to shared IP pools or requiring strict Single Sign-On (SSO) session affinity egress directly via the clean host public IPv4 address, eliminating unnecessary latency and rate-limiting penalties.
4. **Localhost Management Isolation:**
   The 3X-UI administrative console is bound exclusively to local loopback addresses and accessed through an encrypted SSH tunnel. External port scanners observe a closed port (`Connection Refused`).
5. **Anti-DMCA Host Protection:**
   Kernel-level L7 filtering inspects and immediately drops packets containing BitTorrent handshake signatures, preventing accidental peer-to-peer file transfers and subsequent hosting provider account suspensions.

---

### 3.1. Deep Analysis: Scanner Detection, Active Probing & Censorship Resistance

Deploying infrastructure in environments subject to active network surveillance (such as state-level deep packet inspection (DPI), active probing systems, and automated internet-wide scanner bots like Censys, Shodan, and Shadowserver) introduces unique threat vectors. This architecture employs multi-layered defenses to achieve operational invisibility:

#### 1. Defense Against Internet-Wide Bot Scanners (Shodan, Censys, Masscan)
* **ICMP Echo Suppression (`net.ipv4.icmp_echo_ignore_all = 1`):** Large-scale reconnaissance crawlers routinely perform ping sweeps across IPv4 ranges before initiating port scans. Discarding all ICMP echo requests renders the host completely silent to automated availability probes.
* **Complete Administrative Interface Concealment:** The 3X-UI control panel is strictly bound to `127.0.0.1:23600` behind an obscure URI token path. External scans directed at port 23600 or the historical default port `2053` encounter a closed socket (`Connection Refused`), eliminating automated banner grabbing (`Server: x-ui`) and brute-force credential attacks.
* **Subscription Endpoint Hygiene:** The public HTTP subscription gateway (`sub-enhancer` on port `2096`) only responds to authenticated cryptographic URI paths (e.g. `/sub_sec_un/<token>`). Scanner probes attempting generic requests (such as `GET /` or `GET /sub`) receive an uninformative `404 Not Found` response with no identifying headers or server fingerprints.

#### 2. Defense Against Active Probing by Censors (DPI & Middlebox Probing Systems)
Active probing is a technique where network inspection middleboxes intercept suspicious TLS handshakes and immediately dispatch follow-up probe packets to the target IP address to verify whether it is a proxy server.
* **Cryptographic Fallback (VLESS Reality):** When an unauthenticated scanner or DPI probe connects to port `443` without the valid Curve25519 client key and `ShortId`, Xray does **not** terminate the connection or return an error packet. Instead, it seamlessly functions as a reverse proxy, relaying the TLS handshake to the genuine target server (`dest`, such as `gateway.icloud.com:443` or `dl.google.com:443`).
* **Authentic TLS Signatures:** Probing entities receive authentic TLS 1.3 certificates signed by trusted Root Certificate Authorities (DigiCert, Google Trust Services), authentic ALPN negotiation (`h2`, `http/1.1`), and authentic HTTP responses directly from Apple or Google servers. The IP address appears completely benign and indistinguishable from a legitimate reverse proxy or CDN edge node.
* **Traffic Fingerprinting Resistance (uTLS & XTLS-Vision):**
  * **uTLS Emulation:** Client software emulates the exact TLS ClientHello byte signatures of standard consumer web browsers (`Chrome`, `Safari`), defeating JA3 and JA4 signature-based heuristic classifiers.
  * **XTLS-Vision Direct Splice:** Eliminates the classic "TLS-in-TLS" double-encryption artifact and applies dynamic packet padding, preventing flow-length analysis from identifying encrypted proxy streams.
* **Multi-SNI Selection Rationale:**
  * `gateway.icloud.com` (Apple Private Relay): Highly effective across mobile cellular networks. Because Apple routes Private Relay traffic across diverse third-party partner autonomous systems (Fastly, Akamai, Cloudflare), DPI systems cannot reliably classify an IP-SNI ASN mismatch as proxy activity without causing catastrophic false positives for iOS device traffic.
  * `dl.google.com` (Google CDN): Optimized for high-throughput broadband fiber connections, leveraging widespread Google global caching infrastructure.

#### 3. Protection Against Copyright Trolls & Automated Abuse Scanners
* **DMCA Crawler Threat Model:** Automated copyright enforcement crawlers monitor public BitTorrent swarms, logging swarm IP addresses and dispatching automated DMCA infringement notices directly to upstream hosting providers.
* **Dual-Layer Kernel & Core Blackholing:**
  * *Kernel Layer:* Linux `iptables` Boyer-Moore string matching drops TCP/UDP packets containing `BitTorrent` protocol signatures at the network layer before processing.
  * *Application Layer:* Xray-core internal routing drops `protocol: ["bittorrent"]` and private subnet traffic into a blackhole outbound (`"protocol": "blackhole"`).
  * This dual-layer enforcement ensures peer-to-peer handshakes are dropped instantly before leaving the server interface, preventing hosting account suspensions.

---

### 3.2. Advanced Anti-Fingerprinting & Evasion Hardening

To prevent automated censorship systems and DPI middleboxes from developing heuristic signatures against deployed infrastructure, operators should implement three strategic countermeasures:

#### 1. SNI Decentralization & Custom Domain Selection
* **The Vulnerability:** When thousands of operators copy generic SNI domains (such as `dl.google.com` or `gateway.icloud.com`) from online guides, state-level DPI systems can easily flag the statistical anomaly of hundreds of unknown hosting provider IP addresses impersonating the same major corporate domain. In some jurisdictions, DPI filters drop connections where the SNI's Autonomous System Number (ASN) does not match the server's actual hosting ASN (*IP-SNI Mismatch Filtering*).
* **Hardening Strategy:**
  * Operators should select **unique, independent masquerade targets** rather than copying public defaults.
  * **Criteria for an Optimal SNI:**
    1. Must natively support **TLS 1.3** and **HTTP/2** (verify with `curl -Iv --tlsv1.3 --http2 https://target.com`).
    2. Must have high, natural daily web traffic from the client's home country so censors cannot blanket-block it without severe collateral damage.
    3. Prefer high-capacity software delivery networks, global open-source CDNs, or enterprise SaaS endpoints (e.g. `swdist.apple.com`, `speed.cloudflare.com`, `cdnjs.cloudflare.com`, `images.unsplash.com`).
    4. Configure multiple independent SNIs under the same Reality inbound to provide instant client-side failover.

#### 2. Non-Standard Subscription Gateway Ports
* **The Vulnerability:** Standard guides deploy web panels and subscription endpoints on predictable default ports (`2053`, `2096`). Network crawlers frequently sweep these specific ports looking for base64 subscription endpoints.
* **Hardening Strategy:**
  * Avoid default ports. Migrate public subscription gateways to random, obscure high ports (e.g. `28443` or `39443`).
  * `sub-enhancer` supports dual-port listening (serving both legacy `2096` and hardened `28443`), allowing zero-downtime client migration.

#### 3. Graceful ShortId Rotation
* **The Vulnerability:** Static Reality `ShortId` strings persisted for months can eventually be recorded in ISP connection telemetry.
* **Hardening Strategy:**
  * Xray Reality supports specifying a comma-separated array of multiple 8-byte hexadecimal strings in `shortIds` (e.g. `["859a72d4fa0c9a5e", "7b3c2e1f4a5d6089", "99aabbccddeeff00"]`).
  * Add a new ShortId to the server array every few months before updating client subscriptions. Older ShortIds remain accepted until all devices sync, preventing unexpected connection drops.

---

## 🛠️ 4. Step-by-Step Deployment Procedure

### Step 0: Swap Allocation (Crucial for 1 GB RAM Nodes)
If the server has ≤ 1.5 GB of physical RAM, allocate a 2 GB swapfile to ensure system stability under sudden traffic spikes:
```bash
if [ $(free -m | awk '/^Mem:/{print $2}') -le 1500 ] && [ $(free -m | awk '/^Swap:/{print $2}') -eq 0 ]; then
    fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
```

---

### Step 1: Kernel Performance & Stealth Configuration
1. **Enable TCP BBR & Fair Queueing:**
   ```bash
   sed -i '/net.core.default_qdisc/d' /etc/sysctl.conf
   sed -i '/net.ipv4.tcp_congestion_control/d' /etc/sysctl.conf
   echo "net.core.default_qdisc=fq" >> /etc/sysctl.conf
   echo "net.ipv4.tcp_congestion_control=bbr" >> /etc/sysctl.conf
   ```
2. **Enable ICMP Blackhole (Stealth Mode):**
   ```bash
   sed -i '/net.ipv4.icmp_echo_ignore_all/d' /etc/sysctl.conf
   echo "net.ipv4.icmp_echo_ignore_all=1" >> /etc/sysctl.conf
   sysctl -p
   ```

---

### Step 2: Layer-7 BitTorrent Filtering (Anti-DMCA)
Install kernel string-matching rules to immediately drop P2P traffic:
```bash
iptables -I FORWARD -p tcp -m string --string "BitTorrent" --algo bm -j DROP
iptables -I FORWARD -p tcp -m string --string "BitTorrent protocol" --algo bm -j DROP
iptables -I FORWARD -p udp -m string --string "BitTorrent" --algo bm -j DROP
iptables -I FORWARD -p udp -m string --string "BitTorrent protocol" --algo bm -j DROP
```
*Persist rules across reboots: On RHEL/Rocky Linux, install `iptables-services` and run `service iptables save`. On Ubuntu/Debian, install `iptables-persistent`.*

---

### Step 3: Deploy Cloudflare WARP SOCKS5 Gateway
Install the official `cloudflare-warp` daemon:

* **For Rocky Linux 9 / AlmaLinux 9:**
  ```bash
  curl -fsSl https://pkg.cloudflareclient.com/cloudflare-warp-ascii.repo | tee /etc/yum.repos.d/cloudflare-warp.repo
  dnf install -y cloudflare-warp
  ```
* **For Ubuntu / Debian:**
  ```bash
  curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg
  echo "deb [arch=amd64 signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/cloudflare-warp.list
  apt update && apt install -y cloudflare-warp
  ```

**Configure WARP in Local Proxy Mode:**
```bash
systemctl enable --now warp-svc
sleep 2
warp-cli --accept-tos register
warp-cli --accept-tos set-mode proxy
warp-cli --accept-tos set-proxy-port 40000
warp-cli --accept-tos connect
```
*Validation:* Verify the output of `curl -x socks5h://127.0.0.1:40000 https://cloudflare.com/cdn-cgi/trace | grep warp` returns `warp=on`.

---

### Step 4: Install 3X-UI & Isolate Panel Access
Deploy the 3X-UI management panel:
```bash
bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh)
```
Ensure the panel web port (e.g. `23600`) is accessible strictly via `localhost` and not exposed to the public network interface.

---

### Step 5: Configure Xray Core Routing (`xrayTemplateConfig`)
Apply the hardened Xray configuration template directing selected AI platforms to the `warp-socks` outbound:

```json
{
  "outbounds": [
    { "tag": "direct", "protocol": "freedom", "settings": {} },
    {
      "tag": "warp-socks",
      "protocol": "socks",
      "settings": {
        "servers": [{ "address": "127.0.0.1", "port": 40000 }]
      }
    },
    { "tag": "blocked", "protocol": "blackhole", "settings": {} }
  ],
  "routing": {
    "domainStrategy": "IPIfNonMatch",
    "rules": [
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
        "outboundTag": "warp-socks",
        "domain": [
          "domain:openai.com",
          "domain:chatgpt.com",
          "domain:oaistatic.com",
          "domain:oaiusercontent.com",
          "domain:ai.com",
          "domain:sora.com",
          "domain:anthropic.com",
          "domain:claude.ai",
          "domain:claude.com",
          "domain:perplexity.ai"
        ]
      }
    ]
  }
}
```

> [!NOTE]
> **Rationale for Selective Multi-Egress Routing:**  
> Modern online services and AI APIs enforce divergent, often opposing IP reputation and fraud detection models:
> * **Datacenter ASN Classification:** Platforms targeting automated scrapers (e.g. OpenAI, Anthropic, Perplexity) frequently challenge or outright block commercial cloud hosting Autonomous System Numbers (ASNs). Routing their domains through an edge-peered proxy such as Cloudflare WARP masks the datacenter origin and satisfies anti-bot Turnstile checks.
> * **Shared Egress Noise & Session Affinity:** In contrast, large-scale consumer ecosystems and identity providers maintain high-volume threat intelligence that heavily rate-limits well-known shared proxy ranges due to widespread abuse. Furthermore, enterprise platforms enforce strict Single Sign-On (SSO) session IP consistency, treating discrepancies between login authentication endpoints and application APIs as security anomalies.
> * **Architectural Balance:** A selective multi-egress policy directs ASN-restricted platforms through the auxiliary edge proxy, while allowing session-sensitive, high-trust services to egress directly via the host's clean dedicated IP. This eliminates CAPTCHAs, maximizes transfer speeds, and guarantees session stability.

---

### Step 6: Configure VLESS Reality & Multi-SNI Endpoints
1. **Primary Inbound:**
   * **Protocol:** `VLESS`
   * **Port:** `443` (TCP)
   * **Security:** `REALITY`
   * **Flow:** `xtls-rprx-vision`
   * **Sniffing:** Enabled for `http`, `tls`, `quic`.
   * **ShortIds Pool:** Specify multiple 8-byte hexadecimal keys in `shortIds` (e.g. `["859a72d4fa0c9a5e", "7b3c2e1f4a5d6089", "99aabbccddeeff00"]`) to enable seamless client key rotation without service disruption.
2. **Masquerade Endpoints (Hosts Tab in 3X-UI):**
   * **Host 1 (Cellular):** SNI: `gateway.icloud.com`, Remark: `Mobile Stealth (Apple iCloud) 📱`.
   * **Host 2 (Broadband Wi-Fi):** SNI: `dl.google.com`, Remark: `Fast Wi-Fi (Google CDN) ⚡`.
   * **Host 3 (CDN Backup):** SNI: `swdist.apple.com`, Remark: `Backup Stealth (Apple CDN) 🛡️`.

---

### Step 7: Deploy Subscription Gateway (`sub-enhancer`)
The subscription enhancer dynamically transforms subscription URLs, assigns explicit remark titles to endpoints, and supports dual-port listening:

* **Executable:** `/usr/local/bin/sub-enhancer.py` (simultaneously listens on standard port `2096` and hardened custom port `28443`, forwarding to 3X-UI internal subscription port `2095`).
* **Systemd Unit:** `/etc/systemd/system/sub-enhancer.service`.
* **Automatic Healing:** Automatically rewrites client URL typos and injects `Profile-Update-Interval: 12` headers.

Enable and start the service:
```bash
systemctl daemon-reload
systemctl enable --now sub-enhancer
```

---

## 📱 5. Client Application Setup & Multi-SNI Profiles

### 5.1. Importing the Encrypted Subscription (Happ / Shadowrocket / v2rayN)
1. Launch the 3X-UI management console via the SSH tunnel tool (`open_panel_localhost.bat` on Windows or `open_panel_localhost.sh` on macOS/Linux).
2. Click the **QR Code** icon next to your client record in the inbound list, and copy the encrypted happ://crypt5/... URL (or direct HTTP subscription URL).
3. Open **Happ** (or Shadowrocket / v2rayN) on your mobile device or computer and add the subscription.
4. **Autonomous Synchronizations:** The subscription header enforces automatic synchronization every 12 hours (Profile-Update-Interval: 12). To manually pull newly added nodes at any time, tap the 🔄 icon inside Happ.

### 5.2. Client-Side Split Tunneling & Routing Policies
To maximize throughput and avoid latency on regional banking, government, and media services:
1. In Happ, set the Rule Order to: **Block → Direct → Proxy**.
2. **Behavior:**
   * Ad trackers and malicious telemetry match **Block** and are discarded immediately.
   * Domestic websites, local banking apps, and low-latency domestic services match **Direct** and bypass the VPN completely, connecting at maximum physical ISP line speeds.
   * International services, AI platforms, streaming networks, and blocked endpoints match **Proxy** and route securely through the hardened remote VPS.

### 5.3. Essential Client DNS & Anti-Loop Configuration
To ensure maximum responsiveness for AI platforms and prevent management lockouts:
* **Server IP Direct Exclusion (Anti-Loop Rule):** In Happ Custom Rules, assign `YOUR_SERVER_IP` ➔ **Direct** (or enable Per-App Split Tunneling for terminal applications). This prevents workstation SSH sessions and panel helper scripts from being captured by the VPN tunnel recursively.
* **Fake DNS (Highly Recommended):** Toggle **Fake DNS: Enabled** (Domain Strategy: `IPIfNonMatch`). Fake DNS responds instantly (<1 ms) with synthetic `198.18.0.x` addresses, eliminating local DNS query latency, bypassing ISP DNS tampering, and preventing hostname resolution timeouts for `gemini.google.com` and `chatgpt.com`.
* **Dual-Zone DNS Split:**
  * **Remote DNS (Proxy Traffic):** Set to Cloudflare DoH (`https://cloudflare-dns.com/dns-query` / `1.1.1.1`) or Google DoH. All resolution occurs safely inside the remote encrypted tunnel.
  * **Local DNS (Direct Traffic):** Set to **System** or local domestic DNS (e.g. `77.88.8.8` / ISP UDP). This guarantees that domestic banking, payment gateways, and government sites resolve via optimal regional CDN nodes without being degraded by international middleboxes.

### 5.4. Administration Helper Scripts (client-tools/)
The repository includes dedicated workstation scripts for secure operations without web browser exposure:
* **`open_panel_localhost.bat` (Windows):** Establishes an encrypted SSH tunnel to the VPS and opens the isolated 3X-UI web interface at `http://localhost:23600/web_secret_path/`.
* **`open_panel_localhost.sh` (macOS / Linux):** Unix counterpart script for shell users (supporting macOS `open` and Linux `xdg-open`).
* **`change_password.bat` (Windows) & `change_password.sh` (macOS / Linux):** Reset the panel administrator password over SSH in one command without logging into the web interface.

---

## 🔧 6. Maintenance, Operations & Troubleshooting Runbook

To maintain 24/7 reliability, systems administrators should adhere to standard operational practices:

### 6.1. Regular Security Maintenance

* **For Rocky Linux 9 / AlmaLinux 9:**
  Audit pending security advisories:
  ```bash
  dnf check-update --security
  ```
  Apply security-specific patches without modifying unaffected packages:
  ```bash
  dnf upgrade --security -y
  ```
  *Recommendation:* Automate critical security patching using the `dnf-automatic` package (`upgrade_type = security`).

* **For Ubuntu / Debian:**
  ```bash
  apt update && apt --only-upgrade install -y $(apt-get --just-print upgrade | awk '/^Inst/{print $2}')
  ```

---

### 6.2. Log Maintenance & Disk Sanitation
Active proxy routing generates steady systemd journal volume. Enforce automatic retention limits:

1. **Vacuum Logs to 7 Days or 200 MB:**
   ```bash
   journalctl --vacuum-time=7d
   journalctl --vacuum-size=200M
   ```
2. **Monitor Available Disk Capacity:**
   ```bash
   df -h /
   ```

---

### 6.3. Service Healthcheck Procedures

Inspect all active components with a single status command:
```bash
systemctl status x-ui warp-svc sub-enhancer --no-pager
```

* **Verify Cloudflare WARP Connectivity:**
  ```bash
  curl -x socks5h://127.0.0.1:40000 -s https://cloudflare.com/cdn-cgi/trace | grep warp
  ```
  *(Expected response: `warp=on`)*
* **Monitor Memory & Processor Load:**
  ```bash
  free -h
  uptime
  ```
* **Inspect Real-Time Bandwidth Utilization:**
  ```bash
  vnstat -d   # Daily traffic summary
  vnstat -m   # Monthly traffic summary
  ```

---

### 6.4. Database Backup Strategy
All client UUIDs, Reality keys, and inbound settings reside inside a single SQLite database file:
* File path: `/etc/x-ui/x-ui.db`

**Perform a Snapshot Backup:**
```bash
cp /etc/x-ui/x-ui.db /etc/x-ui/x-ui_backup_$(date +%F).db
```
To restore a snapshot, copy the backup file back to `/etc/x-ui/x-ui.db` and execute `systemctl restart x-ui`.

---

### 6.5. Troubleshooting Runbook

1. **Client Connection Failures:**
   * Check Xray daemon status: `systemctl status x-ui`.
   * Review recent runtime logs: `journalctl -u x-ui -n 50 --no-pager`.
2. **AI Platforms Reporting "Access Denied":**
   * Restart and re-register the WARP service:
     ```bash
     systemctl restart warp-svc && sleep 2 && warp-cli --accept-tos connect
     ```
3. **Panel Inaccessible via SSH Tunnel:**
   * Confirm the local SSH tunnel process is active on your workstation, and verify the local listening port on the server:
     ```bash
     ss -tlpn | grep 23600
     ```

---

### 6.6. Verification of Server Stealth & Scanner Invisibility (Audit Runbook)

System operators can verify their server's stealth posture and confirm resistance to scanners using standard diagnostic utilities executed from an external workstation:

#### 1. Verify Management Interface Isolation
Execute a port scan targeting the administrative port and standard panel ports from an external workstation:
```bash
nmap -Pn -p 22,443,2096,2053,23600 <YOUR_VPS_IP>
```
* **Expected Result:**
  * Port `22` (SSH): `open`
  * Port `443` (VLESS Reality): `open`
  * Port `2096` (Subscription Gateway): `open`
  * Ports `2053` and `23600` (Panel): `closed` or `filtered` (Zero external exposure)

#### 2. Verify VLESS Reality Active Probing Fallback
Simulate an unauthenticated probe on port 443 using `openssl`:
```bash
openssl s_client -connect <YOUR_VPS_IP>:443 -servername gateway.icloud.com -showcerts < /dev/null
```
* **Expected Result:**
  * The handshake succeeds, displaying the authentic DigiCert SSL certificate issued to `*.icloud.com` / `gateway.icloud.com`.
  * No proxy signatures, self-signed certificates, or Xray identifiers are leaked.

#### 3. Verify ICMP Ping Blackhole Mode
Send ICMP echo requests to the server IP:
```bash
ping -c 4 <YOUR_VPS_IP>
```
* **Expected Result:** `100% packet loss` (The server ignores ping probes entirely).

#### 4. Verify Subscription Gateway Sanitization
Test an unauthenticated HTTP request against the public subscription port:
```bash
curl -I http://<YOUR_VPS_IP>:2096/
```
* **Expected Result:** `HTTP/1.0 404 Not Found` (or empty response) with zero disclosure of internal subscription endpoints or 3X-UI headers.

---

## 📄 License

This blueprint is published under the terms of the [MIT License](LICENSE). You are free to adapt, extend, and deploy these configurations in personal or institutional network environments.

---

## ⚠️ Educational Disclaimer & Operational Liability Notice

This documentation, architectural blueprint, and deployment automation scripts are provided strictly for educational, technical research, and informational evaluation purposes.

1. **Informational & Educational Scope:** The materials contained in this guide reflect technical engineering observations and reference configurations. They do not constitute guaranteed production warranties or legal guidance.
2. **Non-Exhaustive Edge Cases:** Due to wide divergences across cloud VPS providers, hypervisor implementations, operating system builds, and regional Deep Packet Inspection (DPI) filtering rules, this blueprint cannot cover every problematic edge case, network anomaly, or platform-specific failure scenario.
3. **Requirement for Individual Analysis & Testing:** System operators are strongly advised to critically analyze all information specifically for their own use case. It is essential to thoroughly test, validate, and verify that these services and configurations function reliably and securely within your specific operating environment, hosting infrastructure, and unique legal/operational circumstances.
4. **Limitation of Liability:** The authors and contributors assume no responsibility or liability for service interruptions, hosting provider account terminations, packet degradation, data loss, or legal consequences resulting from the deployment, modification, or operational use of this blueprint.
