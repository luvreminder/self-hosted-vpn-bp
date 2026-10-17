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
print("\n[+] 2. Обслуживание пула маскировки Reality (SNI) и криптографическая ротация Short IDs...")
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
    
    # КРИТИЧЕСКИ ВАЖНО: В Reality все serverNames обязаны строго совпадать с SAN сертификата dest!
    # Нельзя смешивать несовместимые домены (Apple, Google, Microsoft) в одном инбаунде.
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
        # Для пользовательских доменов и Self-SNI (Steal Oneself) сохраняем текущие имена
        current_names = reality.get("serverNames", [])
        dest_host = dest_target.split(":")[0]
        valid_snis = current_names if current_names else [dest_host]
        sni_label_map = {s: f"Custom Stealth ({s}) 🔒" for s in valid_snis}

    reality["serverNames"] = valid_snis
    
    # Ротация Short IDs: удаляем скомпрометированные публичные ключи из шаблонов GitHub!
    public_compromised_sids = {
        "859a72d4fa0c9a5e", "7b3c2e1f4a5d6089", "99aabbccddeeff00",
        "0123456789abcdef", "1234567890abcdef"
    }
    existing_sids = set(reality.get("shortIds", [])) - public_compromised_sids
    
    # Генерируем свежие криптографически стойкие 8-байтные hex-токены
    while len(existing_sids) < 4:
        existing_sids.add(secrets.token_hex(8))
    
    sorted_sids = sorted(list(existing_sids))
    reality["shortIds"] = sorted_sids
    stream["realitySettings"] = reality
    
    cur.execute("UPDATE inbounds SET stream_settings=? WHERE id=1;", (json.dumps(stream),))
    print(f"[OK] Reality Inbound #1 обновлен:")
    print(f"     Dest: {dest_target}")
    print(f"     Сертифицированные SAN SNI ({len(valid_snis)}): {', '.join(valid_snis)}")
    print(f"     Криптографические Short IDs ({len(sorted_sids)}): {', '.join(sorted_sids)}")

# -------------------------------------------------------------
# ШАГ 3: Актуализация описаний узлов в подписке (hosts table)
# -------------------------------------------------------------
print("\n[+] 3. Обновление каталога маскировок в подписках (Sub-Enhancer)...")
# Определяем локацию сервера для корректного отображения страны в клиентах
try:
    import urllib.request
    with urllib.request.urlopen("http://ip-api.com/json/?fields=country,countryCode", timeout=2.5) as r:
        geo_info = json.loads(r.read().decode())
        c_code = geo_info.get("countryCode", "")
        flag = "".join(chr(127397 + ord(c)) for c in c_code.upper()) if len(c_code) == 2 else "🌐"
        geo_prefix = f"{flag} {geo_info.get('country', 'VPS')}"
except Exception:
    geo_prefix = "🛡️ Stealth"

# Синхронизируем таблицу hosts строго с валидным пулом SNI текущего инбаунда
for order, sni in enumerate(valid_snis, start=1):
    base_label = sni_label_map.get(sni, f"CDN {sni}")
    remark = f"{geo_prefix} • {base_label}"
    sort_order = order * 10
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

# Деактивируем несовместимые SNI от старых конфигураций
placeholders = ",".join("?" for _ in valid_snis)
cur.execute(f"UPDATE hosts SET is_disabled=1 WHERE inbound_id=1 AND sni NOT IN ({placeholders});", tuple(valid_snis))
conn.commit()
print(f"[OK] {len(valid_snis)} узлов подписки успешно синхронизированы с SAN сертификата dest.")

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
                            if not host and (k in ("IP", "HOST", "SERVER_IP", "SERVER") or "IP СЕРВЕРА" in k):
                                if v and not v.startswith("YOUR_") and not v.startswith("<"):
                                    host = v
                            if not port and (k in ("SSH_PORT", "PORT") or "ПОРТ" in k):
                                try:
                                    port = int(v)
                                except ValueError:
                                    pass
                            if not user and (k in ("SSH_USER", "USER", "USERNAME") or "ПОЛЬЗОВАТЕЛЬ" in k):
                                if v and not v.startswith("YOUR_"):
                                    user = v
                            if not password and (k in ("PASSWORD", "SSH_PASSWORD", "ROOT_PASSWORD") or any(x in k for x in ["SSH ПАРОЛЬ", "ROOT ПАРОЛЬ", "ПАРОЛЬ ROOT", "ПАРОЛЬ"])):
                                if v and not v.startswith("YOUR_") and not v.startswith("<"):
                                    password = v
                            if not key_path and (k in ("SSH_KEY_PATH", "SSH_KEY", "KEY_PATH", "KEY") or "КЛЮЧ" in k):
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

