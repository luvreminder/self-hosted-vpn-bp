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

* **Production-Grade Isolation:** The 3X-UI panel is bound strictly to `localhost` and accessible only through an encrypted SSH tunnel. The server operates in Stack Mimicry mode (active ICMP echo responses for client speedometer accuracy and middlebox camouflage) or optional Silent Blackhole mode.
* **Intelligent Outbound Split-Routing:** High-performance direct egress for streaming, gaming, and general web browsing, combined with transparent, selective routing through a local Cloudflare WARP SOCKS5 proxy (`127.0.0.1:40000`) exclusively for AI platforms.
* **Multi-SNI Disguise Profiles:** Independent server masquerades tailored for cellular networks and broadband Wi-Fi, strictly validated against the target server's SAN certificate.
* **Automated Subscription Gateway (`sub-enhancer`):** An autonomous background daemon that resolves dynamic node labels from SQLite, normalizes URL input errors, enforces localhost / TLS isolation, and injects automatic 12-hour background refresh headers.
* **Host & Protocol Abuse Protection:** Dual-tier anti-BitTorrent protection combining Xray Core deep protocol sniffing (`protocol: ["bittorrent"] -> blackhole`) with kernel-level packet filters.
* **Universal Compatibility:** Fully tested across modern enterprise Linux (Rocky Linux 9, AlmaLinux 9) and Debian-family releases (Ubuntu 22.04/24.04, Debian 12).
* **Active Probing Defense & Comprehensive Stealth:** Stack Mimicry defense (active ICMP echo for client latency benchmarks, or optional Silent Blackhole) coupled with VLESS Reality cryptographic fallback to genuine Apple and Google TLS 1.3 endpoints. Unauthenticated probes receive authentic third-party SSL certificates, while uTLS and XTLS-Vision neutralize heuristic DPI fingerprinting.

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
  * [3.3. State-of-the-Art (SOTA) DPI Evasion: Mitigating L7 Behavioral Flow Analysis & Stream Freezes](#33-state-of-the-art-sota-dpi-evasion-mitigating-l7-behavioral-flow-analysis--stream-freezes)
* [🛠️ 4. Step-by-Step Deployment Procedure](#️-4-step-by-step-deployment-procedure)
  * [Step 0: Swap Allocation](#step-0-swap-allocation-crucial-for-1-gb-ram-nodes)
  * [Step 1: Kernel Performance & Stealth](#step-1-kernel-performance--stealth-configuration)
  * [Step 2: Layer-7 BitTorrent Filtering](#step-2-layer-7-bittorrent-filtering-anti-dmca)
  * [Step 3: Deploy Cloudflare WARP Egress (Native WireGuard / SOCKS5)](#step-3-deploy-cloudflare-warp-egress-for-ai-platforms)
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
  * [6.7. Operational Best Practices: Critical Dos and Don'ts](#67-operational-best-practices-critical-dos-and-donts)
* [🔄 7. Routine & Monthly VPS Maintenance Runbook](#-7-routine--monthly-vps-maintenance-runbook)
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
* **Multi-SNI Selection Rationale & Foreign SNI Nuances:**
  * `gateway.icloud.com` (Apple Private Relay): Highly resilient on mobile cellular networks because Apple distributes egress across partner CDNs (Fastly, Akamai, Cloudflare), reducing simple ASN mismatch triggers.
  * `dl.google.com` (Google CDN): High-throughput broadband caching endpoints.
  * **Critical Foreign SNI Vulnerability (Active Probe Latency & ASN Mismatch):**  
    When a commercial VPS (e.g. Hetzner, OVH, Aeza) presents an SNI belonging to Google or Apple, DPI probes can measure the round-trip latency difference (RTT) between the VPS's TCP `SYN-ACK` (<10ms) and the TLS `ServerHello` forwarded from `dest` (+30–80ms). Furthermore, all `serverNames` in a single Reality inbound **must strictly belong to the SAN of the certificate served by `dest`**; mismatched SNIs cause immediate probe TLS errors.
  * **Self-SNI / Steal Oneself:** The ultimate countermeasure to Foreign SNI active probing is hosting a lightweight local web service (via Nginx or Caddy with a real Let's Encrypt certificate) on `127.0.0.1:8443` and pointing Reality `dest` to it. This produces 0 ms forwarding latency and 100% ASN parity.

#### 3. Protection Against Copyright Trolls & Automated Abuse Scanners
* **DMCA Crawler Threat Model:** Automated copyright enforcement crawlers monitor public BitTorrent swarms, logging swarm IP addresses and dispatching automated DMCA infringement notices directly to upstream hosting providers.
* **Dual-Layer Core & Kernel Enforcement:**
  * *Application Layer (Xray Core):* Because Xray is a userspace proxy, proxy client traffic terminates at `INPUT` and originates new connections at `OUTPUT`, completely bypassing `iptables FORWARD`. Deep protocol sniffing inside Xray Core (`protocol: ["bittorrent"] -> blackhole`) is the primary engine that inspects packet structures and drops BitTorrent handshakes (including encrypted MSE/PE flows).
  * *Kernel Layer (`iptables OUTPUT`):* Linux `iptables` Boyer-Moore string matching drops any accidental P2P packets generated directly by host-level processes.
  * This dual-layer architecture prevents BitTorrent traffic from ever leaving the server interface, eliminating hosting account suspensions.

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

### 3.3. State-of-the-Art (SOTA) DPI Evasion: Mitigating L7 Behavioral Flow Analysis & Stream Freezes

In adversarial censorship environments and restrictive national firewall perimeters, state-level censorship appliances have advanced far beyond traditional static IP blacklists and TLS SNI string matching. Modern Deep Packet Inspection (DPI) platforms actively utilize **Layer-7 Behavioral Flow Analysis** and state-table timeout manipulation. Understanding these failure modes and deploying state-of-the-art countermeasures is essential for maintaining perpetual tunnel availability.

#### 1. The "16 KB Stream Freeze" Failure Mode in Raw TCP Reality
* **The Failure Mechanism:** A client successfully establishes a classic `VLESS + TCP + Reality` (with `xtls-rprx-vision`) connection. The initial TLS 1.3 handshake is cryptographically indistinguishable from the target disguise server (`dest`) and completes in ~100 ms. However, as soon as continuous application data flows over the raw TCP socket (typically after 16 KB to 64 KB of payload transfer), L7 DPI flow-inspection engines analyze the packet size distribution, timing intervals, and long-lived continuous data streams to a commercial datacenter IP.
* **The Symptom:** Rather than injecting an overt `TCP RST`, the middlebox **silently drops subsequent TCP data packets**. On the server, executing `ss -tnp` reveals a clogged `Send-Q` backlog containing un-acknowledged bytes. On the client workstation, browser requests hang indefinitely and time out (`HTTP 000` / `ERR_TIMED_OUT`), while speed tests report `n/a`.
* **SOTA Countermeasure — VLESS + XHTTP (SplitHTTP v2) over Reality & TLS:**
  * In modern Xray Core (v25+ / v26+), **XHTTP** is the official next-generation anti-censorship transport, superseding legacy WebSocket and gRPC.
  * Instead of maintaining an exposed, raw TCP stream, XHTTP fragments proxy payload into discrete, genuine HTTP/2 request-response pairs with randomized chunk padding (`mode: auto`).
  * Combining `network: xhttp` with `security: reality` provides the gold standard: the initial connection mimics authentic third-party TLS certificates, while subsequent traffic flows inside standard HTTP/2 multiplexed streams that completely neutralize the middlebox "16 KB raw TCP stream freeze".

#### 2. The TCP KeepAlive Desync Trap & Idle Connection Resets
* **The Failure Mechanism:** Default Linux distributions configure the kernel TCP keepalive timeout to `net.ipv4.tcp_keepalive_time = 7200` (2 hours). However, stateful middleboxes (such as ISP DPI boxes, carrier-grade NATs, and national firewalls) maintain active connection tracking tables with aggressive expiration windows of **30 to 60 seconds**.
* **The Symptom:** Whenever a user pauses browsing (e.g. reading an article for 45 seconds), the middlebox purges the connection tracking state. When the server or client transmits the next packet, the middlebox treats it as an untracked packet and immediately injects a **`TCP RST` (Connection Reset by Peer)**. Users experience constant, frustrating disconnections even on functional protocols.
* **SOTA Countermeasure — Anti-DPI Kernel Tuning & Socket KeepAlive:**
  * Configure aggressive kernel-level TCP keepalive probes so that idle connections emit lightweight probe frames every 20 seconds, preventing middlebox state table eviction:
    ```ini
    net.ipv4.tcp_keepalive_time = 20
    net.ipv4.tcp_keepalive_intvl = 5
    net.ipv4.tcp_keepalive_probes = 4
    ```
  * In Xray inbound configurations, set `streamSettings.sockopt`:
    ```json
    "sockopt": {
      "tcpKeepAliveInterval": 15,
      "tcpKeepAliveIdle": 15,
      "tcpUserTimeout": 10000
    }
    ```

#### 3. Dynamic DNS (DDNS) Flakiness & ISP DNS Poisoning
* **The Failure Mechanism:** Deploying personal server endpoints via third-party dynamic DNS services introduces a fragile external dependency. Public DDNS subdomains have near-zero TTLs and are heavily targeted by restrictive ISPs with DNS throttling, packet drops, or synthetic NXDOMAIN poisoning.
* **The Symptom:** Client applications attempting to reconnect or perform periodic health checks fail with domain resolution timeouts, severing active proxy tunnels.
* **SOTA Countermeasure — Direct IP Endpoints with Preserved TLS SNI:**
  * Configure the subscription gateway (`sub-enhancer`) to emit direct server IPv4 addresses as the connection endpoint in client URLs (`vless://uuid@<SERVER_IP>:port?...`), while preserving the authentic domain inside the `sni` parameter.
  * The client connects directly to the IP address with zero DNS overhead or poisoning risk, while the TLS handshake negotiates and verifies the genuine domain certificate without errors.

#### 4. The ICMP Blackhole vs Client Latency Measurement Dilemma
* **The Conflict:** Complete ICMP echo suppression (`net.ipv4.icmp_echo_ignore_all = 1`) protects servers from automated wide-area ping scanners. However, popular modern proxy clients (such as Happ, v2rayN, and Shadowrocket) evaluate subscription node health and latency by dispatching **ICMP Echo (Ping) probes**.
* **The Symptom:** When ICMP is discarded, client latency tests report `n/a` (Not Available) for all unselected nodes, misleading users into believing the infrastructure is offline.
* **SOTA Countermeasure — Controlled ICMP Echo:**
  * Enable ICMP echo replies (`net.ipv4.icmp_echo_ignore_all = 0`) to provide instant, accurate latency benchmarks in client applications, while relying on loopback binding, secret token URIs, and firewall rules to protect administrative interfaces.

#### 5. Advanced XHTTP XMUX Session Rotation & Asymmetric Routing
* **The Failure Mechanism:** Long-lived HTTP/2 streams that transfer sustained volume over a single persistent TCP connection trigger behavioral flow heuristics in state-level Layer-7 DPI appliances. Legitimate web browsing consists of transient connections that cycle periodically.
* **SOTA Countermeasure — `xmux` Multiplexing Control:**
  Configure the `xmux` parameters in `xhttpSettings`:
  ```json
  "xmux": {
    "maxConcurrency": 16,
    "cMaxReuseTimes": 600,
    "cMaxLifetimeMs": 1800000,
    "hMaxRequestTimes": 800,
    "hMaxReusableSecs": 2400
  }
  ```
  Xray smoothly recycles TCP/TLS connections every 600–800 requests or 30–40 minutes in the background without dropping user sessions, perfectly mimicking organic browser traffic.
* **Asymmetric Up/Down Routing (Bypassing 16KB Host Subnet Filters):**
  When DPI applies aggressive RST filtering to outbound connections targeting foreign VPS subnets (the "16KB host filter"), XHTTP allows separating flows:
  - **Uplink:** Client requests route via Cloudflare / CDN using `packet-up` over HTTP/3 QUIC.
  - **Downlink:** High-throughput server responses return directly to the client.
  Because DPI observes only unidirectional flows towards disparate IP addresses, bidirectional session analysis fails completely.

#### 6. Single Port 443 Architecture (SNI Router & Multiplexer)
* **The Failure Mechanism:** Exposing a constellation of auxiliary ports (`443`, `8443`, `2083`, `2096`, `28443`) on a single VPS IP creates a signature fingerprint readily indexed by automated Internet scanners (Censys, Shodan) and DPI categorizers.
* **SOTA Countermeasure — Layer-4 SNI Preread Multiplexing:**
  Only port 443 (and SSH) is exposed publicly. Nginx runs with `ssl_preread on;` in a `stream` block, reading the TLS ClientHello SNI without terminating encryption:
  - `SNI = dl.google.com`: Forwarded to Inbound #1 (Reality with `dest: dl.google.com:443`).
  - `SNI = gateway.icloud.com`: Forwarded to Inbound #2 (Reality with `dest: gateway.icloud.com:443`). Multi-SNI across distinct corporations on port 443 with zero SAN certificate conflicts!
  - `SNI = yourdomain.com`: Forwarded to local web server (Nginx HTTP/2 terminating with Let's Encrypt), which serves a genuine decoy website at `/`, handles VLESS XHTTP over a secret path, and reverse-proxies `/sub_sec_un/` to Sub-Enhancer (`127.0.0.1:2096`) over trusted HTTPS on standard port 443!
  - Auxiliary ports `2096`, `28443`, `8443`, and `2083` are bound exclusively to `127.0.0.1` and permanently closed in the external firewall.

#### 7. Native Userspace WireGuard Outbound in Xray Core (Eliminating `warp-svc`)
* **The Problem with `warp-svc`:** The official Cloudflare WARP client daemon consumes ~100 MB RAM, requires kernel `tun` modules and DBus, conflicts with older glibc libraries, and suffers UDP dropouts in SOCKS5 mode (forcing operators to block UDP 443 / QUIC for AI domains).
* **SOTA Countermeasure — Native Userspace WireGuard in Xray Core:**
  Xray Core natively supports `"protocol": "wireguard"` in outbounds without external daemons. Using the included `generate_warp_wireguard.py` helper, a free Cloudflare WARP account is registered via API in 1 second, extracting `privateKey`, assigned IPv4/IPv6, peer public key, and the mandatory 3 `reserved` bytes.
  - **0 MB Background Daemon RAM:** No external packages or services needed.
  - **Native UDP & QUIC Support:** Eliminates the need to block QUIC (UDP:443) for AI services.
  - **Universal Virtualization Support:** Operates seamlessly even in restricted LXC / OpenVZ containers where `/dev/net/tun` is unavailable.

#### 8. Client-Side TLS Hello Fragmentation (`fragment`) for Direct TLS
* **The Failure Mechanism:** Generic dynamic DNS hostnames or unlisted personal domains often have their domain strings targeted via regex pattern matching in the unencrypted TLS ClientHello packet.
* **SOTA Countermeasure — TLS Hello Packet Segmentation:**
  Xray Core and compatible clients support outbound TLS fragmentation:
  ```json
  "fragment": {
    "packets": "tlshello",
    "length": "10-20",
    "interval": "10-15"
  }
  ```
  By segmenting the initial TLS ClientHello packet into 10–20 byte TCP fragments separated by 10–15 ms, the plaintext SNI string is broken across multiple TCP packets. High-speed wire DPI hardware cannot reassemble fragmented TCP segments at multi-gigabit line rate, bypassing domain filtering without throughput penalty.

#### 9. Stack Mimicry: Why `icmp_echo_ignore_all = 0` Outperforms Ping Suppression
* **Modern Scanner Reality:** Global IP scanners (Censys, Shodan, ZMap) scan the entire IPv4 space directly with TCP SYN probes to port 443 (`-Pn`), ignoring ICMP ping completely.
* **DPI ML Heuristics:** Legitimate edge nodes (Google, Apple, Cloudflare) universally respond to ICMP Echo. A server that silently drops ICMP while presenting an open TCP 443 port presents an obvious TCP/IP stack anomaly to behavioral classifiers.
* **The Resolution:** Maintain `net.ipv4.icmp_echo_ignore_all = 0` (Stack Mimicry) for client speed test compatibility and realistic edge behavior, while relying strictly on Single Port 443 and localhost binding to prevent reconnaissance discovery.

#### 10. Alternative UDP Transport: Hysteria 2 / QUIC with Layer-4 Port Hopping
* **The Problem with Pure TCP:** Under aggressive cellular throttling, mobile handoffs, or severe packet loss (5–15%), TCP tunnels suffer from TCP Meltdown and Head-of-Line blocking.
* **SOTA Countermeasure — Hysteria 2 Coexistence on Port 443/UDP:**
  Because TCP and UDP maintain distinct socket namespaces in Linux, **port 443/TCP (VLESS Reality / XHTTP) and port 443/UDP (Hysteria 2 QUIC) run concurrently on the exact same port 443 without collision**.
  - **Brutal Congestion Control:** Maintains maximum link throughput even under 15–20% packet loss.
  - **iptables Port Hopping:** Evades dynamic UDP port throttling by mapping ports 20000–50000 to port 443:
    ```bash
    iptables -t nat -A PREROUTING -p udp --dport 20000:50000 -j REDIRECT --to-ports 443
    ```

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

### Step 1: Kernel Performance & Anti-DPI Tuning
1. **Enable TCP BBR & Fair Queueing:**
   ```bash
   sed -i '/net.core.default_qdisc/d' /etc/sysctl.conf
   sed -i '/net.ipv4.tcp_congestion_control/d' /etc/sysctl.conf
   echo "net.core.default_qdisc=fq" >> /etc/sysctl.conf
   echo "net.ipv4.tcp_congestion_control=bbr" >> /etc/sysctl.conf
   ```
2. **Apply Anti-DPI TCP KeepAlive Tuning:**
   Prevents middlebox connection-tracking table expiration and eliminates random TCP RST resets during idle periods:
   ```bash
   sed -i '/net.ipv4.tcp_keepalive_time/d' /etc/sysctl.conf
   sed -i '/net.ipv4.tcp_keepalive_intvl/d' /etc/sysctl.conf
   sed -i '/net.ipv4.tcp_keepalive_probes/d' /etc/sysctl.conf
   echo "net.ipv4.tcp_keepalive_time=20" >> /etc/sysctl.conf
   echo "net.ipv4.tcp_keepalive_intvl=5" >> /etc/sysctl.conf
   echo "net.ipv4.tcp_keepalive_probes=4" >> /etc/sysctl.conf
   ```
3. **Configure ICMP Ping Handling:**
   * *Stack Mimicry & Client Latency Mode (Default — Recommended for client app speedometers and middlebox camouflage):*
     ```bash
     sed -i '/net.ipv4.icmp_echo_ignore_all/d' /etc/sysctl.conf
     echo "net.ipv4.icmp_echo_ignore_all=0" >> /etc/sysctl.conf
     sysctl -p
     ```
   * *Silent Blackhole Mode (Optional for mass-scanner evasion):*
     ```bash
     sed -i '/net.ipv4.icmp_echo_ignore_all/d' /etc/sysctl.conf
     echo "net.ipv4.icmp_echo_ignore_all=1" >> /etc/sysctl.conf
     sysctl -p
     ```

---

### Step 2: Layer-7 BitTorrent Filtering (Anti-DMCA)

> [!IMPORTANT]
> **Userspace Proxy vs Kernel Packet Filtering:**  
> Xray Core operates as a userspace application. Inbound proxy traffic connects to the server's TCP socket (`INPUT` chain), where Xray decrypts the stream and initiates independent outbound TCP/UDP sessions (`OUTPUT` chain). Client proxy traffic **never traverses the kernel `FORWARD` chain**!  
> Furthermore, modern BitTorrent clients employ Message Stream Encryption (MSE/PE) and uTP/DHT, which renders simple string matching inside packets ineffective against modern P2P traffic.  
> **True Layer-7 Protection:** Real anti-torrent protection is enforced directly within the Xray Core routing engine via deep protocol sniffing (`"protocol": ["bittorrent"] -> "blocked"`).  
> The kernel `iptables` rules below provide complementary defense-in-depth on the `OUTPUT` and `FORWARD` chains to prevent rogue host processes or forwarding daemons from participating in torrent swarms:

```bash
iptables -I OUTPUT -p tcp -m string --string "BitTorrent" --algo bm -j DROP
iptables -I OUTPUT -p udp -m string --string "BitTorrent" --algo bm -j DROP
iptables -I FORWARD -p tcp -m string --string "BitTorrent" --algo bm -j DROP
iptables -I FORWARD -p udp -m string --string "BitTorrent" --algo bm -j DROP
```
*Persist rules across reboots: On RHEL/Rocky Linux, run `service iptables save`. On Ubuntu/Debian, install `iptables-persistent` and run `netfilter-persistent save`.*

---

### Step 3: Deploy Cloudflare WARP Egress for AI Platforms

#### Option A: Next-Gen Native Userspace WireGuard in Xray Core (Recommended)
This approach eliminates the `cloudflare-warp` daemon, saving ~100 MB of RAM, resolving glibc conflicts, and providing full UDP/QUIC forwarding for AI services:
```bash
# Generate WireGuard keys and register with Cloudflare client API
python3 generate_warp_wireguard.py --update-template xray_template_config.json --output /etc/x-ui/warp_wireguard.json
```
*Validation:* Verify `/etc/x-ui/warp_wireguard.json` is generated with `tag: warp-wireguard`, assigned IPv4/IPv6, and 3-byte `reserved` parameters.

#### Option B: Legacy Cloudflare WARP SOCKS5 Daemon (Fallback)
If manual daemon management is preferred:
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
*Validation:* Verify `curl -x socks5h://127.0.0.1:40000 https://cloudflare.com/cdn-cgi/trace | grep warp` returns `warp=on`.

---

### Step 4: Install 3X-UI & Isolate Panel Access
Deploy the 3X-UI management panel and programmatically isolate it strictly to `127.0.0.1` in the database to prevent exposure to public internet scanners:
```bash
bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh)

# Stop x-ui to safely update database settings and prevent race conditions
systemctl stop x-ui

# Strictly bind panel and internal subscription daemon to localhost (IPv4 127.0.0.1)
sqlite3 /etc/x-ui/x-ui.db << 'EOF'
INSERT INTO settings (key, value) VALUES ('webListen', '127.0.0.1') ON CONFLICT(key) DO UPDATE SET value=excluded.value;
INSERT INTO settings (key, value) VALUES ('webPort', '23600') ON CONFLICT(key) DO UPDATE SET value=excluded.value;
INSERT INTO settings (key, value) VALUES ('webBasePath', '/web_secret_path/') ON CONFLICT(key) DO UPDATE SET value=excluded.value;
INSERT INTO settings (key, value) VALUES ('subListen', '127.0.0.1') ON CONFLICT(key) DO UPDATE SET value=excluded.value;
INSERT INTO settings (key, value) VALUES ('subPort', '2095') ON CONFLICT(key) DO UPDATE SET value=excluded.value;
INSERT INTO settings (key, value) VALUES ('subEnable', 'true') ON CONFLICT(key) DO UPDATE SET value=excluded.value;
INSERT INTO settings (key, value) VALUES ('subPath', '/sub/') ON CONFLICT(key) DO UPDATE SET value=excluded.value;
INSERT INTO settings (key, value) VALUES ('subURI', 'http://<YOUR_VPS_IP>:2096/sub/') ON CONFLICT(key) DO UPDATE SET value=excluded.value;
INSERT INTO settings (key, value) VALUES ('subJsonPath', '/json_sub/') ON CONFLICT(key) DO UPDATE SET value=excluded.value;
INSERT INTO settings (key, value) VALUES ('subJsonURI', 'http://<YOUR_VPS_IP>:2096/json_sub/') ON CONFLICT(key) DO UPDATE SET value=excluded.value;
INSERT INTO settings (key, value) VALUES ('subJsonEnable', 'true') ON CONFLICT(key) DO UPDATE SET value=excluded.value;
EOF

# Option 1: Next-Gen Single Port 443 Firewall (Recommended)
# Exposes ONLY Port 443 (TCP/UDP) and SSH (22/tcp). All other services multiplex internally.
ufw default deny incoming && ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 443/tcp comment 'VLESS-REALITY-443'
ufw allow 443/udp comment 'Hysteria2-QUIC-443'
ufw --force enable

# Option 2: Standard Multi-Port Firewall (Public Gateway Mode)
# ufw allow 80/tcp comment 'Sub-Gateway-HTTP-Universal'
# ufw allow 2096/tcp comment 'Sub-Gateway-Direct'
# ufw allow 28443/tcp comment 'Sub-Gateway-Alt'
# ufw allow 8443/tcp comment 'Direct-TLS'
# ufw allow 2083/tcp comment 'XHTTP'

systemctl start x-ui
```

---

### Step 5: Configure Xray Core Routing (`xrayTemplateConfig`)
Apply the hardened Xray configuration template directing selected AI platforms to the `warp-socks` outbound.

> [!CAUTION]
> **API and Stats Sections Required:**  
> The `api`, `stats`, `policy`, and `dokodemo-door` sections must be present in `xrayTemplateConfig`. Omitting them breaks 3X-UI user traffic statistics, bandwidth accounting, and client expiration tracking!

```json
{
  "api": {
    "tag": "api",
    "services": [
      "HandlerService",
      "LoggerService",
      "StatsService",
      "RoutingService"
    ]
  },
  "stats": {},
  "policy": {
    "levels": {
      "0": {
        "statsUserUplink": true,
        "statsUserDownlink": true
      }
    },
    "system": {
      "statsInboundUplink": true,
      "statsInboundDownlink": true,
      "statsOutboundUplink": true,
      "statsOutboundDownlink": true
    }
  },
  "inbounds": [
    {
      "tag": "api",
      "listen": "127.0.0.1",
      "port": 62789,
      "protocol": "dokodemo-door",
      "settings": {
        "address": "127.0.0.1"
      }
    }
  ],
  "outbounds": [
    {
      "tag": "direct",
      "protocol": "freedom",
      "settings": {
        "domainStrategy": "UseIPv4"
      },
      "streamSettings": {
        "sockopt": {
          "tcpKeepAliveIdle": 20,
          "tcpKeepAliveInterval": 5
        }
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
  ],
  "routing": {
    "domainStrategy": "IPIfNonMatch",
    "rules": [
      {
        "type": "field",
        "inboundTag": [
          "api"
        ],
        "outboundTag": "api"
      },
      {
        "type": "field",
        "outboundTag": "blocked",
        "protocol": [
          "bittorrent"
        ]
      },
      {
        "type": "field",
        "outboundTag": "blocked",
        "ip": [
          "geoip:private"
        ]
      },
      {
        "type": "field",
        "outboundTag": "blocked",
        "domain": [
          "geosite:category-ads-all"
        ]
      },
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
        "domain": [
          "geosite:openai",
          "geosite:anthropic",
          "geosite:perplexity",
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
          "domain:anthropic.com",
          "domain:claude.ai",
          "domain:claude.com",
          "domain:cursor.sh",
          "domain:cursor.com",
          "domain:cursor-cdn.com",
          "domain:copilot.microsoft.com",
          "domain:perplexity.ai",
          "domain:midjourney.com",
          "domain:x.ai",
          "domain:grok.com",
          "domain:deepseek.com",
          "domain:mistral.ai",
          "domain:cohere.com"
        ]
      },
      {
        "type": "field",
        "outboundTag": "direct",
        "network": "tcp,udp"
      }
    ]
  },
  "dns": {
    "servers": [
      "1.1.1.1",
      "8.8.8.8",
      "1.0.0.1",
      "localhost"
    ],
    "queryStrategy": "UseIPv4"
  }
}
```

> [!NOTE]
> **Why Block QUIC (UDP 443) for AI Domains?**  
> Cloudflare WARP in SOCKS5 proxy mode (`127.0.0.1:40000`) only proxies TCP connections. When mobile apps (such as the ChatGPT and Claude apps) attempt HTTP/3 (QUIC over UDP:443), packets are dropped or hang indefinitely, resulting in eternal loading spinners. Blocking UDP:443 for AI domains forces client web browsers and mobile apps to immediately fallback to stable, high-speed TCP/TLS.

---

### Step 6: Configure VLESS Reality & Multi-SNI Endpoints

1. **Primary Inbound:**
   * **Protocol:** `VLESS`
   * **Port:** `443` (TCP)
   * **Security:** `REALITY`
   * **Flow:** `xtls-rprx-vision`
   * **Sniffing:** Enabled for `http`, `tls`, `quic`.
   * **ShortIds Pool:** Generate random 8-byte hexadecimal tokens (e.g. `python3 -c "import secrets; print(secrets.token_hex(8))"`). **Never reuse public sample shortIds from GitHub!**

2. **Crucial Rule for Reality Multi-SNI (SAN Certificate Matching):**
   > [!WARNING]
   > In VLESS Reality, all domains specified in `serverNames` **MUST belong to the Subject Alternative Names (SAN) of the certificate returned by the `dest` server!**  
   > **Do NOT mix Apple, Google, Microsoft, and Samsung domains into a single inbound!**  
   > If your `dest` is `gateway.icloud.com:443`, an active censorship probe connecting with `SNI = www.microsoft.com` will receive Apple's certificate (`*.icloud.com`) from your server. The scanner detects the certificate mismatch and immediately flags and blocks your IP.

   * **Apple Inbound (`dest = gateway.icloud.com:443`):**
     * SNI Pool: `gateway.icloud.com`, `configuration.apple.com`, `swdist.apple.com`, `updates.cdn-apple.com`, `appleid.apple.com`.
   * **Google Inbound (`dest = dl.google.com:443`):**
     * SNI Pool: `dl.google.com`, `www.google.com`, `fonts.googleapis.com`.
   * **Self-SNI / Steal Oneself (Ultimate Stealth Tier):**
     * For zero latency probe RTT and 100% ASN matching, host a real static website on the VPS using Nginx or Caddy on `127.0.0.1:8443` with a genuine Let's Encrypt TLS certificate for your own domain. Point Reality `dest` to `127.0.0.1:8443`. Active probes will see 0 ms internal RTT and matching ASN, making detection mathematically indistinguishable from a legitimate web server.

---

### Step 7: Deploy Subscription Gateway (`sub-enhancer`)

> [!CAUTION]
> **Subscription Security & Mobile Client Architecture:**  
> 1. **Public Gateway Mode (Default in `universal_deploy.sh`):** `sub-enhancer.py` binds to `0.0.0.0` on ports `80`, `2096`, and `28443` to enable seamless over-the-air subscription updates on mobile devices (Happ on iOS/Android, Shadowrocket, v2rayN). Subscriptions are distributed over plain HTTP on standard port 80 or port 2096 using obscure cryptographic tokens (`/sub_sec_un/<token>`) to prevent URL enumeration and bypass ISP high-port blocks.  
> 2. **SSL / TLS Warning for Subscriptions:** Do **NOT** use self-signed TLS certificates for subscription endpoints. Mobile OS trust stores reject self-signed certificates (`SSLHandshakeException` / `x509: certificate signed by unknown authority`), breaking subscription updates. Furthermore, raw IP addresses cannot be accessed via `https://` without a custom IP-SAN certificate. Only enable TLS (`SUB_ENABLE_TLS=true`) if you have bound a valid domain with a genuine CA certificate (e.g. Let's Encrypt).  
> 3. **Zero-Exposure Mode (SSH-Only):** For paranoid zero-exposure operations, set `SUB_LISTEN=127.0.0.1` and close ports 80/2096/28443 in the firewall. Clients must then update subscriptions exclusively through local SSH port forwarding (`client-tools/open_panel_localhost`).

* **Executable:** `/usr/local/bin/sub-enhancer.py` (normalizes URL typos, injects `hosts` table labels, and adds `Profile-Update-Interval: 12` headers).
* **Systemd Unit:** `/etc/systemd/system/sub-enhancer.service`.

Enable and start the service:
```bash
systemctl daemon-reload
systemctl enable --now sub-enhancer
```

---

## 📱 5. Client Application Setup & Multi-SNI Profiles

### 5.1. Importing the Subscription (Happ / Shadowrocket / v2rayN / v2rayNG)
1. **Locate your Sub-Enhancer Gateway URL:** Do not import raw un-enhanced loopback links (`http://127.0.0.1:23600/...`) directly from the panel. Use the public Sub-Enhancer Gateway distribution endpoint configured during deployment:
   * **Universal Unblocked Format (Recommended for Mobile / Raw IP):**  
     `http://<YOUR_VPS_IP>/sub_sec_<prefix>/<token>`  
     *(Standard port 80 plain HTTP; universally bypasses ISP high-port throttling, avoids SSL certificate mismatch, and works on all mobile carriers).*
   * **Direct Gateway Format (Port 2096 HTTP):**  
     `http://<YOUR_VPS_IP>:2096/sub_sec_<prefix>/<token>`
   * **Domain TLS Format (With Let's Encrypt Certificate):**  
     `https://<YOUR_DOMAIN>:2096/sub_sec_<prefix>/<token>`  
     *(Only use HTTPS if connecting via a registered domain matching your Let's Encrypt TLS certificate).*
   * **Sing-box JSON Profile (For Sing-box / Happ Advanced JSON):**  
     `http://<YOUR_VPS_IP>/json_sec_<prefix>/<token>` or `https://<YOUR_DOMAIN>:2096/json_sec_<prefix>/<token>`
   *(The credentials summary and deployment script outputs the exact token URL, e.g., `/sub_sec_un/un_vip_2026`).*
2. Open **Happ** (or Shadowrocket / v2rayN / v2rayNG) on your device and import the subscription URL.
3. **Autonomous Synchronizations:** The subscription header enforces automatic synchronization every 12 hours (`Profile-Update-Interval: 12`). To manually pull newly updated nodes or shortIds at any time, tap the 🔄 refresh icon inside your client.
4. **Selecting Resilient Node Profiles:**
   * **Domestic / Fixed Broadband:** Choose `Germany • Samsung CDN Ultra ⚡ (TCP Reality Vision)` for lowest overhead and maximum throughput.
   * **Cellular Data & Restrictive Networks (Middlebox IP-ASN Heuristics):** Select **`Antarctica • Direct TLS Fast ⚡`** (port 8443) or **`Antarctica • ICEbreaker (XHTTP) 🧊`** (port 2083). These nodes use your registered server domain (Self-SNI) and discrete HTTP/2 chunking to bypass active middlebox RST injection.

### 5.2. Client-Side Split Tunneling & Routing Policies
To maximize throughput and avoid latency on regional banking, government, and media services:
1. In Happ, set the Rule Order to: **Block → Direct → Proxy**.
2. **Behavior & Operational Nuances:**
   * **Block:** Ad trackers, telemetry, and malicious domains (`geosite:category-ads-all`) are discarded immediately.
   * **Direct:** Domestic websites, local banking apps, and low-latency local services (e.g. `geosite:category-domestic`, `geoip:domestic`, or your resident country code) bypass the VPN completely, connecting at maximum physical ISP line speeds.
     * *Nuance Note:* Some international blocked resources may use domestic CDN nodes, while certain regional services may utilize foreign cloud IPs. Keep your client's GeoSite and GeoIP routing databases updated.
   * **Proxy:** International services, AI platforms, streaming networks, and blocked endpoints match **Proxy** and route securely through the hardened remote VPS.
   * **IPv6 Leak Protection:** If your local ISP provides IPv6, ensure your client is set to prefer IPv4 (`UseIPv4` / `IPv4 Preferred`) or disable IPv6 tunneling if the VPS egress uses dedicated IPv4. This eliminates silent DPI leaks and connection resets over unmonitored IPv6 routes.

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
4. **Subscription Download Timeout in Client Apps (e.g., `timeout (7s)`):**
   * Confirm that the client VPN (TUN mode or system proxy) is temporarily **switched off** before updating subscriptions, preventing recursive proxy deadlocks.
   * Verify the `sub-enhancer` daemon is active: `systemctl status sub-enhancer`.
   * Ensure subscription ports (`80`, `2096`, `28443`) are reachable and permitted in the firewall: `firewall-cmd --list-ports` or `ufw status`.
   * If updating subscriptions over cellular mobile data (MTS, Tele2, MegaFon, Beeline) or restricted Wi-Fi, use the **Port 80 HTTP URL** (`http://<YOUR_VPS_IP>/sub_sec_.../<token>`), as carrier middleboxes frequently drop or throttle traffic to high non-standard ports like 2096 and 28443.
5. **VLESS Reality Handshake Timing Out:**
   * Confirm that the client's SNI exactly matches one of the domains listed in `realitySettings.serverNames` for Inbound #1. Unlisted SNIs are rejected by Xray as unauthorized probes.
   * Confirm that the client uses an authorized `shortId` present in `realitySettings.shortIds`.
   * If regional DPI middleboxes throttle foreign tech SNIs (`www.google.com`), connect using the Self-SNI / Direct TLS profile on port `8443`.
6. **Handshake Succeeds but Data Stream Freezes After ~16 KB (L7 DPI Behavioral Flow Analysis):**
   * *Symptom:* Tunnel establishes, initial ping responds, but opening web pages, video streams, or downloading files stalls indefinitely (`HTTP 000` / timeout).
   * *Diagnosis:* Run `ss -tnp` on the server while the client attempts to stream. If the client socket displays a clogged `Send-Q` buffer (e.g. 1000–2000 un-ACKed bytes) that never clears, the regional middlebox DPI has identified raw TCP proxy flow characteristics and is silently blackholing payload packets without emitting RST.
   * *Resolution:* Migrate Inbound #1 from `network: tcp` to `network: xhttp` with `security: reality` and `mode: auto` (or deploy an XHTTP TLS inbound). XHTTP encapsulates proxy traffic within standard, discrete HTTP/2 requests with randomized chunking, completely evading stream-level DPI classification.
7. **Connection Constantly Drops / Resets During Idle Periods or Video Streams (Middlebox State Timeout):**
   * *Symptom:* Connection frequently resets after pauses in browsing (30–60 seconds of inactivity); client logs report `connection reset by peer` (TCP RST).
   * *Diagnosis:* Inspect Linux kernel keepalive: `sysctl net.ipv4.tcp_keepalive_time`. If set to default `7200` (2 hours), middlebox stateful firewalls drop connection tracking states after 30–60 seconds of silence, rejecting subsequent packets.
   * *Resolution:* Apply anti-DPI kernel keepalive parameters (`net.ipv4.tcp_keepalive_time=20`, `net.ipv4.tcp_keepalive_intvl=5`, `net.ipv4.tcp_keepalive_probes=4`) and enable socket keepalive in Xray inbound `streamSettings.sockopt` (`"tcpKeepAliveInterval": 15`).
8. **Nodes Display "n/a" Latency in Client Applications (Happ, v2rayN):**
   * *Symptom:* The active connected node displays latency (e.g. 120 ms), but all unselected nodes in the subscription list display `n/a` (Not Available).
   * *Diagnosis:* Popular clients (such as Happ) utilize ICMP Echo (Ping) to measure latency across subscription nodes. If the server has `net.ipv4.icmp_echo_ignore_all = 1` enabled, ICMP packets are silently dropped.
   * *Resolution:* Enable ICMP echo replies on the server: `sysctl -w net.ipv4.icmp_echo_ignore_all=0` (and persist in `/etc/sysctl.conf`).
9. **Periodic Proxy Disconnections Due to Dynamic DNS (DDNS) Instability:**
   * *Symptom:* Client tunnels drop intermittently; client logs indicate DNS lookup errors or resolution timeouts for public dynamic DNS hostnames.
   * *Diagnosis:* Restrictive ISPs aggressively throttle, poison, or fail to resolve low-TTL free DDNS subdomains.
   * *Resolution:* In `sub-enhancer`, configure direct IP addressing (`SUB_CONNECT_IP=<SERVER_IP>`) so client configurations connect directly to the server IP while keeping the genuine domain in the `sni` parameter for TLS validation.

---

### 6.6. Verification of Server Stealth & Scanner Invisibility (Audit Runbook)

System operators can verify their server's stealth posture and confirm resistance to scanners using standard diagnostic utilities executed from an external workstation:

#### 1. Verify Management & Subscription Interface Isolation
Execute a port scan targeting the administrative port and subscription ports from an external workstation:
```bash
nmap -Pn -p 22,80,443,2095,2096,28443,2053,23600 <YOUR_VPS_IP>
```
* **Expected Result (Public Gateway Mode — Default):**
  * Port `22` (SSH): `open`
  * Port `443` (VLESS Reality): `open`
  * Ports `80`, `2096` (and optionally `28443` if TLS enabled) (`sub-enhancer` Gateway): `open` (Enables frictionless over-the-air subscription updates on mobile devices; endpoint paths are protected by cryptographic tokens `/sub_sec_...`).
  * Ports `2053`, `23600` (Panel) and `2095` (Internal 3X-UI): `closed` or `filtered` (Zero external exposure; accessible exclusively via encrypted SSH tunnel).
* **Expected Result (Zero-Exposure Mode / Single-Port Surface):**
  * Port `22` (SSH): `open`
  * Port `443` (VLESS Reality): `open`
  * Ports `80`, `2053`, `2095`, `2096`, `28443`, `23600`: `closed` or `filtered` (All web interfaces and subscription endpoints sealed behind SSH port forwarding or local loopback).

#### 2. Verify VLESS Reality Active Probing Fallback
Simulate an unauthenticated probe on port 443 using `openssl`:
```bash
openssl s_client -connect <YOUR_VPS_IP>:443 -servername gateway.icloud.com -showcerts < /dev/null
```
* **Expected Result:**
  * The handshake succeeds, displaying the authentic DigiCert SSL certificate issued to `*.icloud.com` / `gateway.icloud.com`.
  * No proxy signatures, self-signed certificates, or Xray identifiers are leaked.

#### 3. Verify ICMP Posture
Send ICMP echo requests to the server IP:
```bash
ping -c 4 <YOUR_VPS_IP>
```
* **Expected Result:**
  * Standard mode (Stack Mimicry): Normal ICMP Echo Replies matching standard web/CDN server behavior and enabling client speedometer tests.
  * Stealth mode (`--stealth-icmp`): `100% packet loss` (Host ignores opportunistic ping sweeps).

#### 4. Verify Subscription Gateway Sanitization (via SSH Tunnel)
With the SSH tunnel active (`client-tools/open_panel_localhost.sh` or `.bat`), test an unauthenticated root request against the local forwarded subscription port:
```bash
curl -I http://127.0.0.1:2096/
```
* **Expected Result:** `HTTP/1.0 404 Not Found` (or empty response) with `Cache-Control: no-store` and `X-Content-Type-Options: nosniff` headers, and zero disclosure of internal 3X-UI fingerprints.

---

### 6.7. Operational Best Practices: Critical Dos and Don'ts

Based on rigorous cross-network diagnostics, live packet tracing, and censorship evasion experiments across hostile ISP middleboxes (including national Layer-7 DPI and carrier-grade middlebox filtering), system administrators must adhere to the following mandatory engineering rules:

#### 1. VLESS Reality SNI & SAN Certificate Alignment
* ❌ **DO NOT mix incompatible domains under a single Reality Inbound:** Never put Apple (`gateway.icloud.com`), Google (`dl.google.com`), and Microsoft (`www.microsoft.com`) together under a single inbound with `dest: dl.google.com:443`.
* ❌ **DO NOT use an SNI that is not listed in `realitySettings.serverNames`:** If an inbound has `dest: dl.google.com:443` and only `www.google.com` in `serverNames`, any client connecting with `dl.google.com` will be rejected by Xray as an unauthorized probe and dropped into fallback, timing out the connection.
* ⚠️ **WHY:** In the Reality protocol, the certificate sent to the client during the TLS handshake is obtained from `dest`. If `dest` is Google, Google returns its own certificate (`*.google.com`). If a client requests `gateway.icloud.com` or `www.microsoft.com`, strict clients immediately abort the connection due to TLS certificate hostname mismatch (`SSL_ERROR_BAD_CERT_DOMAIN`). Moreover, active DPI probes that inspect the returned certificate against the requested SNI immediately flag the VPS as a Reality proxy server.
* ✅ **DO:** Ensure every entry in `realitySettings.serverNames` is a valid Subject Alternative Name (SAN) of the target `dest` certificate. Synchronize the `hosts` table strictly with this validated pool.

#### 2. Short ID Backwards Compatibility & Rotation
* ❌ **DO NOT purge existing production Short IDs during automated rotation:** Never replace `realitySettings.shortIds` with completely fresh random values without retaining previously provisioned client keys.
* ⚠️ **WHY:** When a client saves a subscription node or manual configuration, it binds to a specific Short ID (e.g., `<PRIMARY_SHORT_ID>`). If a maintenance script regenerates `shortIds` from scratch without backward compatibility, all existing client apps instantly fail to establish the Reality handshake.
* ✅ **DO:** Maintain a persistent set of active production Short IDs. When introducing new tokens or retiring compromised sample keys, ensure the primary production Short ID remains active.

#### 3. URL Query Parameter Encoding in Subscription Gateways (`spx`)
* ❌ **DO NOT unescape percent-encoded slashes (`%2F`) into raw slashes (`/`) in subscription URLs:** Avoid regexes like `re.sub(r"([?&]spx=)%2[fF]", r"\g<1>/", line)`.
* ⚠️ **WHY:** While RFC 3986 permits raw `/` inside query components under certain conditions, many mobile and desktop client URL parsers (Happ, Sing-box, v2rayN, FoXray, Streisand) split parameters using regexes like `[^/?#]+` or treat raw `/` as a path delimiter. This truncates or corrupts subsequent query parameters, specifically dropping `flow=xtls-rprx-vision`. Without the Vision flow parameter, direct XTLS streaming fails.
* ✅ **DO:** Keep `spx=%2F...` properly percent-encoded at all times.

#### 4. Server-Side Xray DNS Architecture: Direct UDP vs DoH
* ❌ **DO NOT configure DNS-over-HTTPS (`https://.../dns-query`) as the primary resolver inside `xrayTemplateConfig`:** Avoid `https://1.1.1.1/dns-query` or `https://8.8.8.8/dns-query` in Xray's internal DNS section.
* ⚠️ **WHY:** DoH requires establishing an encrypted TLS connection to port 443 of the resolver for each lookup. When combined with client-side FakeDNS (where domains are sniffed from synthetic `198.18.0.x` IPs) and `domainStrategy: "IPIfNonMatch"`, recursive DoH resolution introduces 300–800 ms latency spikes, socket exhaustion, or complete DNS lockups if the upstream host throttles outbound port 443 to foreign DNS providers.
* ✅ **DO:** Configure fast, direct UDP/TCP DNS resolvers (`1.1.1.1`, `8.8.8.8`, `1.0.0.1`, `localhost`) with `queryStrategy: "UseIPv4"`.

#### 5. Subscription Gateway Network Binding & Firewall Ports
* ❌ **DO NOT bind `sub-enhancer` exclusively to `127.0.0.1` unless all clients use SSH tunnels:**
* ❌ **DO NOT omit subscription ports (`80`, `2096`, `28443`) from firewall rules in Public Gateway mode:**
* ❌ **DO NOT force self-signed TLS certificates on subscription endpoints:**
* ⚠️ **WHY:** If `sub-enhancer.service` specifies `SUB_LISTEN=127.0.0.1` or the firewall blocks subscription ports, mobile clients (Happ on iOS/Android, Shadowrocket, v2rayNG) cannot fetch or refresh node lists over cellular data or Wi-Fi, resulting in persistent connection timeouts (`Failed to download subscription: timeout (7s)`). Cellular operators (MTS, Tele2, MegaFon, Beeline) frequently throttle or drop non-standard ports (`2096`, `28443`); standard port `80` guarantees universal unhindered delivery. Furthermore, mobile OS trust stores strictly reject self-signed certificates (`SSLHandshakeException` / `x509: certificate signed by unknown authority`), permanently preventing users from fetching subscriptions.
* ✅ **DO:** Bind `SUB_LISTEN` to `0.0.0.0`, open ports `80`, `2096`, and `28443` in UFW / firewalld, and secure subscription endpoints using secret tokens (e.g. `/sub_sec_.../<token>`). Serve over plain HTTP on raw IP addresses (e.g. `http://<IP>/sub_sec_.../<token>` or `http://<IP>:2096/...`). If TLS/HTTPS distribution is desired, configure a real public domain with a genuine CA-signed Let's Encrypt certificate and enable `SUB_ENABLE_TLS=true`.

#### 6. Mitigating State-Level Middlebox IP-ASN Discrepancy (ASN Neighbor Scavenging & Self-SNI)
* ❌ **DO NOT rely on overused foreign big-tech SNIs (e.g. `www.samsung.com`) or Cloudflare Anycast domains:**
* ⚠️ **WHY & THE CLOUDFLARE TRAP:**
  1. **IP-ASN Mismatch:** Modern middleboxes (especially on cellular operators like MTS, Tele2, MegaFon, Beeline) cross-reference the TLS `ClientHello` SNI against the destination IP's Autonomous System Number (ASN). If a packet with `SNI = www.samsung.com` (Samsung AS20940 / Akamai) arrives at an unrelated VPS datacenter IP, the DPI flags it as proxy masquerade and injects `TCP RST` or drops packets. Furthermore, `www.samsung.com` was historically hardcoded in 3X-UI templates and is on priority DPI blacklists.
  2. **The Cloudflare Anycast Trap:** Borrowing domains behind Cloudflare (or other Anycast CDNs) does NOT bypass ASN inspection. Although Cloudflare has millions of Anycast IPs worldwide, all of them are announced strictly under Cloudflare's own ASNs (predominantly **AS13335**). If your VPS is hosted on another provider ASN, `VPS IP ≠ AS13335` immediately triggers the mismatch drop. Additionally, active censor probes forwarded to Cloudflare edge nodes return `cf-ray` error headers and TLS mismatches that instantly identify a proxy server.
* ✅ **DO (SOTA 2026 Solutions):**
  1. **In-Network ASN Scavenging («Сосед по ASN / подсети» — Recommended for Zero-Domain Reality):** Scan your VPS provider's local subnet (e.g. your `/24` block) using tools like `RealiTLScanner` or TLS probes to find a legitimate neighbor website hosted in the **exact same Autonomous System (ASN)** that supports **TLS 1.3** and **ALPN h2**. Set that neighbor domain in `serverNames` and `dest`. When DPI checks `IP ∈ ASN(SNI)`, the check passes with 100% success because both your VPS and the donor reside in the identical network, with <0.5 ms handshake latency!
  2. **Self-SNI / Direct TLS (Zero-Discrepancy Backup):** Provide a Direct TLS node on port 8443 using your actual server domain and a genuine Let's Encrypt certificate. Because the domain genuinely resolves to your VPS IP, there is zero ASN discrepancy across all fixed and cellular carriers.

#### 7. Client-Side Troubleshooting: Circular Proxy Lockouts & Per-App Split Tunneling
* ❌ **DO NOT refresh a failing subscription in client apps while TUN mode is active on a dead node:**
* ❌ **DO NOT assume VPN failure when testing non-proxied applications in Per-App Split Tunneling mode:**
* ⚠️ **WHY:** 
  1. When a client app (like Happ) has TUN mode enabled with a broken proxy selected, the operating system routes all outbound traffic into the non-functional tunnel. When the client attempts to update its subscription from the VPS gateway, the update request is trapped inside the dead proxy, resulting in a false-negative timeout.
  2. In client applications like Happ, Sing-box, or NekoBox, Per-App Routing (Split Tunneling) restricts proxy routing strictly to listed binaries (`process_path`). Unlisted software (such as Microsoft Edge, command-prompt `curl` or `ping`, and background system updaters) bypass the VPN tunnel and connect directly (`final: direct`). Testing connection health via terminal or unlisted browsers will observe unproxied ISP traffic, creating false impressions of total node failure. Furthermore, ensure the imported subscription profile is toggled ON (`enabled: true`) in client subscription management.
* ✅ **DO:** Temporarily toggle the VPN connection switch OFF before adding or refreshing subscriptions in client applications, ensure the VPS subscription profile is toggled ON, and test connectivity using an application explicitly included in the client's proxy rule list (such as Google Chrome, Firefox, or Telegram).

#### 8. TCP KeepAlive Tuning Against Middlebox State Drops
* ❌ **DO NOT leave Linux kernel TCP keepalive at default 7200s on proxy hosts:**
* ⚠️ **WHY:** Stateful middlebox firewalls (e.g., national Layer-7 DPI appliances, enterprise perimeter firewalls, and carrier-grade NAT) discard idle connection states after 30–60 seconds of inactivity. When client or server traffic resumes after a pause, the middlebox rejects untracked packets and injects a `TCP RST`, causing constant connection drops. In Linux, sysctl `net.ipv4.tcp_keepalive_*` sets host kernel defaults, but applies only to sockets with `SO_KEEPALIVE`. In Go-based Xray-core, socket keepalive is governed by Go runtime defaults and `streamSettings.sockopt`.
* ✅ **DO:** Configure aggressive TCP keepalive (`net.ipv4.tcp_keepalive_time = 20`, `net.ipv4.tcp_keepalive_intvl = 5`, `net.ipv4.tcp_keepalive_probes = 4`) AND explicitly set Xray socket options (`streamSettings.sockopt.tcpKeepAliveIdle: 20`, `tcpKeepAliveInterval: 5`) across inbounds and outbounds.

#### 9. Direct IP Addressing & Sing-box JSON Address Normalization
* ❌ **DO NOT export bare dynamic DNS hostnames as the connection address in client subscription links:**
* ❌ **DO NOT forward raw upstream 3X-UI Sing-box JSON subscriptions without address rewriting:**
* ⚠️ **WHY:** 
  1. Adversarial ISPs aggressively throttle, poison, or fail to resolve free public dynamic DNS subdomains. When a client reconnects or switches networks, DNS lookup failure severs the proxy tunnel.
  2. When 3X-UI exports profiles in Sing-box JSON format (`/json_sec_...`) through a local reverse proxy (`http://127.0.0.1:2095`), 3X-UI automatically populates the inbound address field with `"address": "localhost"`. If `sub-enhancer` does not inspect and normalize JSON streams, client applications import nodes configured to connect to loopback `127.0.0.1` on the user's local device, resulting in immediate connection rejection (`Connection refused`).
* ✅ **DO:** Configure `sub-enhancer` to emit the direct server IP address as the connection host (e.g. `vless://uuid@<SERVER_IP>:port`) while preserving the actual domain in the `sni` parameter for TLS certificate verification. For Sing-box JSON subscriptions, `sub-enhancer` must intercept and substitute `"address": "localhost"` with the public IPv4 (`SUB_PUBLIC_IP` / `SUB_CONNECT_IP`).

#### 10. XHTTP Transport & Client-Side TLS Fragmentation (`sockopt.fragment`)
* ❌ **DO NOT rely exclusively on raw `VLESS + TCP + Reality` in regions with active Layer-7 behavioral DPI:**
* ⚠️ **WHY:** Modern DPI middleboxes analyze TCP flow characteristics, packet sizes, and durations, freezing raw TCP proxy streams after ~16 KB of payload data. Furthermore, hardware DPI parsers intercept the first packet of a TCP session (`TLS ClientHello`) and extract the plaintext `server_name` (SNI) string to feed their ASN validation modules.
* ✅ **DO (SOTA 2026 Defense-in-Depth):**
  1. **Server-Side: VLESS + XHTTP + Reality:** Deploy `network: xhttp` with `security: reality` and `mode: auto` on port 443. XHTTP encapsulates proxy data within genuine, discrete HTTP/2 requests with randomized chunk padding (`xPaddingBytes: 100-1000`) and multiplexing (`xmux`), completely eliminating stream-level and timing-based DPI classification.
  2. **Client-Side: TLS ClientHello Fragmentation (`sockopt.fragment`):** In client apps (Happ, Sing-box, Xray), enable low-level TCP handshake fragmentation (`packets: 1-3`, `length: 10-30`, `interval: 10-15`). By splitting the `ClientHello` packet across multiple microscopic TCP segments right through the middle of the SNI domain name, high-speed line-rate DPI inspectors fail to reassemble the full SNI in the initial packet buffer and let the connection pass unhindered.

#### 11. ICMP Echo Configuration vs Client Latency Measurement
* ❌ **DO NOT leave ICMP echo completely disabled if end-users rely on client-side latency tests (speedometers):**
* ⚠️ **WHY:** Many client apps (such as Happ) utilize ICMP ping to test server availability across subscription lists. Disabling ICMP echo causes all nodes to display `n/a` (Not Available), creating false impressions of server failure.
* ✅ **DO:** Balance security and usability: enable ICMP echo (`net.ipv4.icmp_echo_ignore_all = 0`) to support client speed tests, while isolating all administrative and non-public service ports behind firewall and SSH tunnel controls.

---

## 🔄 7. Routine & Monthly VPS Maintenance Runbook

> **💡 The Censorship Resistance Lifecycle Principle:**  
> A proxy server degrades over time not from software faults, but from shifts in the external network environment: DPI middleboxes update SNI heuristics, AI platforms introduce new auth endpoints, and OS packages accrue security CVEs. Regular monthly maintenance guarantees 100% service uptime and perpetual immunity to censorship blocking.

### 🤖 7.1. Automated Zero-Touch Systemd Timer
A recurring systemd maintenance timer is configured to run automatically:
* **Maintenance Executable:** `/usr/local/bin/vps-monthly-maintenance.sh`
* **Systemd Timer:** `vps-maintenance.timer` (scheduled for the **1st of every month at 04:30 AM**).
* **Automated Actions:**
  1. Fetches freshest anti-censorship routing databases (`x-ui update-all-geofiles`).
  2. Flushes SQLite write-ahead log and defragments the database (`PRAGMA wal_checkpoint(TRUNCATE); VACUUM;`).
  3. Vacuums systemd journal logs older than 14 days or exceeding 100MB.
  4. Verifies Cloudflare WARP health and re-registers the daemon if dropped.
  5. Gracefully restarts `x-ui` and `sub-enhancer` to apply updated geo-rules.

```bash
# Check scheduled timer status
systemctl list-timers | grep vps-maintenance

# Review latest maintenance execution logs
journalctl -u vps-maintenance.service -n 30 --no-pager
```

---

### 📋 7.2. Step-by-Step Manual Maintenance Checklist
For on-demand audits or manual refreshes:

1. **OS Security Packages:**
   ```bash
   dnf upgrade -y --security  # On Enterprise Linux (Rocky / AlmaLinux)
   # apt update && apt upgrade -y  # On Ubuntu / Debian
   ```
2. **Sync Anti-Censorship Geo-Databases:**
   ```bash
   x-ui update-all-geofiles
   ```
3. **Rotate Reality Short IDs:**
   Generate a new 8-byte hex key (`openssl rand -hex 8`) and append it to the `shortIds` array under Inbound #1 in 3X-UI without deleting existing keys.
4. **Optimize SQLite Database:**
   ```bash
   systemctl stop x-ui
   sqlite3 /etc/x-ui/x-ui.db "PRAGMA wal_checkpoint(TRUNCATE); VACUUM; PRAGMA integrity_check;"
   systemctl start x-ui
   ```
5. **Verify Cloudflare WARP Egress:**
   ```bash
   curl -s -x socks5h://127.0.0.1:40000 https://www.cloudflare.com/cdn-cgi/trace | grep -E "warp=|loc="
   ```
6. **Prune Stale Logs:**
   ```bash
   journalctl --vacuum-time=14d --vacuum-size=100M
   ```
7. **Audit Fail2ban Jail:**
   ```bash
   fail2ban-client status sshd
   ```

---

### ⚡ 7.3. One-Click Remote Maintenance Script
Operators on Windows, macOS, or Linux workstations can trigger the entire maintenance cycle in a single command using [run_monthly_maintenance.py](run_monthly_maintenance.py):

```bash
python community-edition/run_monthly_maintenance.py
```

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
