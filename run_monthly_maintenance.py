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

print("[+] === НАЧАЛО ЕЖЕМЕСЯЧНОГО ТЕХНИЧЕСКОГО ОБСЛУЖИВАНИЯ VPS ===")

DB_PATH = "/etc/x-ui/x-ui.db"

# -------------------------------------------------------------
# ШАГ 1: Обновление GeoIP и GeoSite баз (RunetFreedom + Loyalsoldier)
# -------------------------------------------------------------
print("\n[+] 1. Обновление антицензурных баз GeoIP и GeoSite...")
try:
    res = subprocess.run(["/usr/bin/x-ui", "update-all-geofiles"], capture_output=True, text=True, timeout=120)
    print(res.stdout.strip())
    print("[OK] Базы GeoIP и GeoSite успешно актуализированы.")
except Exception as e:
    print(f"[!] Ошибка обновления гео-баз: {e}")

# -------------------------------------------------------------
# ШАГ 2: Обслуживание Reality маскировок (SNI) и ротация Short IDs
# -------------------------------------------------------------
print("\n[+] 2. Обслуживание пула маскировки Reality (SNI) и добавление новых Short IDs...")
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("SELECT id, stream_settings FROM inbounds WHERE id=1;")
row = cur.fetchone()
if row:
    stream = json.loads(row[1])
    reality = stream.get("realitySettings", {})
    
    # Расширенный пул проверенных TLS 1.3 CDN эндпоинтов для маскировки трафика
    expanded_snis = [
        "gateway.icloud.com",
        "dl.google.com",
        "swdist.apple.com",
        "updates.cdn-apple.com",
        "configuration.apple.com",
        "www.microsoft.com",
        "www.samsung.com",
        "fota-cloud-dn.ospserver.net",
        "www.speedtest.net"
    ]
    reality["serverNames"] = expanded_snis
    
    # Ротация Short IDs: сохраняем старые + добавляем 2 свежих криптографических 8-байтных ключа
    current_sids = set(reality.get("shortIds", []))
    # Гарантируем наличие базовых
    base_sids = ["859a72d4fa0c9a5e", "7b3c2e1f4a5d6089", "99aabbccddeeff00"]
    for sid in base_sids:
        current_sids.add(sid)
    
    while len(current_sids) < 5:
        current_sids.add(secrets.token_hex(8))
    
    sorted_sids = sorted(list(current_sids))
    reality["shortIds"] = sorted_sids
    stream["realitySettings"] = reality
    
    cur.execute("UPDATE inbounds SET stream_settings=? WHERE id=1;", (json.dumps(stream),))
    print(f"[OK] Reality Inbound #1 обновлен:")
    print(f"     SNI эндпоинты ({len(expanded_snis)}): {', '.join(expanded_snis[:4])} ...")
    print(f"     Short IDs ({len(sorted_sids)}): {', '.join(sorted_sids)}")

# -------------------------------------------------------------
# ШАГ 3: Актуализация описаний узлов в подписке (hosts table)
# -------------------------------------------------------------
print("\n[+] 3. Обновление каталога маскировок в подписках (Sub-Enhancer)...")
sni_descriptions = [
    ("gateway.icloud.com", "🇦🇶 Antarctica • Mobile Stealth (Apple iCloud) 📱", 10),
    ("dl.google.com", "🇦🇶 Antarctica • Fast Wi-Fi (Google CDN) ⚡", 20),
    ("swdist.apple.com", "🇦🇶 Antarctica • Apple Services CDN 🛡️", 30),
    ("updates.cdn-apple.com", "🇦🇶 Antarctica • Apple System CDN 🍏", 40),
    ("www.microsoft.com", "🇦🇶 Antarctica • Windows / Microsoft CDN 💻", 50),
    ("www.samsung.com", "🇦🇶 Antarctica • Samsung Ecosystem 📡", 60),
    ("fota-cloud-dn.ospserver.net", "🇦🇶 Antarctica • Samsung FOTA CDN 📲", 70),
    ("www.speedtest.net", "🇦🇶 Antarctica • Ookla Ultra CDN 🚀", 80),
]

for sni, remark, sort_order in sni_descriptions:
    cur.execute("SELECT id FROM hosts WHERE inbound_id=1 AND sni=?;", (sni,))
    h_row = cur.fetchone()
    if h_row:
        cur.execute("UPDATE hosts SET remark=?, sort_order=?, is_disabled=0 WHERE id=?;", (remark, sort_order, h_row[0]))
    else:
        cur.execute(
            "INSERT INTO hosts (inbound_id, sni, remark, sort_order, is_disabled, security, created_at, updated_at) "
            "VALUES (1, ?, ?, ?, 0, 'same', strftime('%s', 'now') * 1000, strftime('%s', 'now') * 1000);",
            (sni, remark, sort_order)
        )

print(f"[OK] {len(sni_descriptions)} узлов подписки с богатыми описаниями синхронизированы.")

# -------------------------------------------------------------
# ШАГ 4: Обновление шаблона маршрутизации Xray (AI Smart Routing)
# -------------------------------------------------------------
print("\n[+] 4. Обновление правил умной маршрутизации нейросетей (AI Smart Routing)...")
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

# Расширенный список ИИ сервисов
ai_domains = [
    # Geosite группы
    "geosite:openai",
    "geosite:anthropic",
    "geosite:google-gemini",
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
    # Google AI / Gemini / AI Studio / Antigravity / Vertex AI / DeepMind
    "domain:gemini.google.com",
    "domain:aistudio.google.com",
    "domain:generativelanguage.googleapis.com",
    "domain:alkalimakersuite-pa.googleapis.com",
    "domain:proactivebackend-pa.googleapis.com",
    "domain:deepmind.google",
    "domain:notebooklm.google",
    "domain:notebooklm.google.com",
    "domain:ai.google.dev",
    "domain:generativeai.google",
    "domain:vertexai.googleapis.com",
    "domain:aiplatform.googleapis.com",
    # Coding & Development AI
    "domain:cursor.sh",
    "domain:cursor.com",
    "domain:cursor-cdn.com",
    "domain:copilot.microsoft.com",
    # Другие популярные ИИ-сервисы
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
            "domain": ["geosite:category-ads-all"]
        },
        # Блокировка QUIC (UDP 443) для ИИ предотвращает зависание приложений в WARP
        {
            "type": "field",
            "outboundTag": "blocked",
            "port": "443",
            "network": "udp",
            "domain": [
                "geosite:openai",
                "geosite:anthropic",
                "geosite:google-gemini",
                "domain:openai.com",
                "domain:chatgpt.com",
                "domain:anthropic.com",
                "domain:claude.ai",
                "domain:gemini.google.com",
                "domain:aistudio.google.com"
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
        "https://1.1.1.1/dns-query",
        "https://8.8.8.8/dns-query",
        "1.1.1.1",
        "8.8.8.8",
        "localhost"
    ],
    "queryStrategy": "UseIPv4"
}

cur.execute("UPDATE settings SET value=? WHERE key='xrayTemplateConfig';", (json.dumps(config, indent=2),))
conn.commit()
conn.close()
print(f"[OK] Шаблон Xray обновлен: {len(ai_domains)} ИИ-доменов перенаправляются через Cloudflare WARP.")

# -------------------------------------------------------------
# ШАГ 5: Обслуживание и компактизация SQLite базы данных
# -------------------------------------------------------------
print("\n[+] 5. Проверка целостности и сжатие базы данных SQLite...")
# Приостанавливаем службу на 2 секунды для безопасного сброса WAL и дефрагментации
subprocess.run(["systemctl", "stop", "x-ui"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
subprocess.run(["sqlite3", DB_PATH, "PRAGMA wal_checkpoint(TRUNCATE); VACUUM;"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
check_res = subprocess.run(["sqlite3", DB_PATH, "PRAGMA integrity_check;"], capture_output=True, text=True)
print(f"[OK] SQLite Integrity Check: {check_res.stdout.strip()}")


# -------------------------------------------------------------
# ШАГ 6: Очистка логов и временных файлов
# -------------------------------------------------------------
print("\n[+] 6. Очистка системных журналов и временных файлов...")
subprocess.run(["journalctl", "--vacuum-time=14d", "--vacuum-size=100M"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
subprocess.run("rm -f /tmp/*.py /tmp/*.json /tmp/*.tmp 2>/dev/null || true", shell=True)
print("[OK] Старые логи и временные файлы удалены.")

# -------------------------------------------------------------
# ШАГ 7: Перезапуск и проверка статуса служб
# -------------------------------------------------------------
print("\n[+] 7. Перезапуск 3X-UI и Sub-Enhancer...")
subprocess.run(["systemctl", "restart", "x-ui"], check=True)
subprocess.run(["systemctl", "restart", "sub-enhancer"], check=True)

# -------------------------------------------------------------
# ШАГ 8: Установка ежемесячного автоматического ТО (Systemd Timer)
# -------------------------------------------------------------
print("\n[+] 8. Настройка автоматического ежемесячного обслуживания (Systemd Timer)...")

maint_script_content = r'''#!/usr/bin/env bash
# Monthly VPS Maintenance Script
set -e
echo "=== [$(date)] Starting Scheduled Monthly Maintenance ==="

# 1. Update GeoIP & GeoSite databases
echo "[*] Updating GeoIP & GeoSite databases..."
/usr/bin/x-ui update-all-geofiles || true

# 2. SQLite maintenance
echo "[*] SQLite VACUUM and WAL Checkpoint..."
sqlite3 /etc/x-ui/x-ui.db "PRAGMA wal_checkpoint(TRUNCATE); VACUUM;" || true

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
echo "[*] Restarting services..."
systemctl restart x-ui || true
systemctl restart sub-enhancer || true

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
# Запуск 1-го числа каждого месяца в 04:30 ночи
OnCalendar=*-*-01 04:30:00
Persistent=true

[Install]
WantedBy=timers.target
'''

with open("/etc/systemd/system/vps-maintenance.timer", "w") as f:
    f.write(timer_unit)

subprocess.run(["systemctl", "daemon-reload"], check=True)
subprocess.run(["systemctl", "enable", "--now", "vps-maintenance.timer"], check=True)
print("[OK] Systemd Timer vps-maintenance.timer активирован (расписание: 1 число каждого месяца в 04:30).")

print("\n=== [✓] ЕЖЕМЕСЯЧНОЕ ТЕХНИЧЕСКОЕ ОБСЛУЖИВАНИЕ УСПЕШНО ЗАВЕРШЕНО ===")
"""

def resolve_credentials(args):
    host = args.host or os.environ.get("VPS_HOST")
    port = args.port or int(os.environ.get("VPS_SSH_PORT", "22"))
    user = args.user or os.environ.get("VPS_USER", "root")
    password = args.password or os.environ.get("VPS_PASSWORD")
    key_path = args.key or os.environ.get("VPS_SSH_KEY")

    # Look for local credentials.txt if not explicitly passed
    for p in ["credentials.txt", "../credentials.txt", os.path.join(os.path.dirname(__file__), "..", "credentials.txt")]:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if not host and "IP сервера:" in line:
                            parts = line.split(":", 1)
                            if len(parts) > 1:
                                host = parts[1].strip()
                        if not password and any(k in line for k in ["SSH Пароль:", "Root Пароль:", "Пароль root:"]):
                            parts = line.split(":", 1)
                            if len(parts) > 1:
                                password = parts[1].strip()
            except Exception:
                pass

    if not key_path:
        default_key = os.path.expanduser("~/.ssh/vps_ed25519")
        if os.path.exists(default_key):
            key_path = default_key

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
        print("[!] Ошибка: IP-адрес сервера не указан.")
        print("    Укажите через аргумент: python run_monthly_maintenance.py --host <IP>")
        print("    Или задайте переменную окружения: set VPS_HOST=<IP>")
        sys.exit(1)

    print(f"[*] Подключение к серверу {host}:{port} (пользователь: {user})...")
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

    print("[*] Передача исполняемого сценария обслуживания...")
    sftp = ssh.open_sftp()
    with sftp.file("/tmp/run_maintenance.py", "w") as f:
        f.write(REMOTE_SCRIPT)
    sftp.close()

    print("[*] Выполнение технического обслуживания на сервере...")
    stdin, stdout, stderr = ssh.exec_command("python3 /tmp/run_maintenance.py", get_pty=True)

    for line in stdout:
        print(line, end="")

    err = stderr.read().decode('utf-8', errors='replace')
    if err:
        print("\n[STDERR]:\n" + err)

    ssh.close()

if __name__ == "__main__":
    main()

