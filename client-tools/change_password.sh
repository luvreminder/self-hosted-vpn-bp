#!/usr/bin/env bash
# ==============================================================================
# 3X-UI Administrator Password Reset (macOS / Linux)
# ==============================================================================
set -euo pipefail

SERVER_IP="YOUR_SERVER_IP"
SSH_PORT="22"
SSH_USER="root"
SSH_KEY="$HOME/.ssh/id_ed25519"
PANEL_USER="admin"

echo "========================================================"
echo " 3X-UI Administrator Password Reset Tool (macOS / Linux)"
echo "========================================================"
echo ""

if [ -n "${1:-}" ]; then
    NEW_PASS="$1"
else
    read -r -s -p "Enter new administrator password: " NEW_PASS
    echo ""
fi

if [ -z "$NEW_PASS" ]; then
    echo "[!] Error: Password cannot be empty." >&2
    exit 1
fi

SSH_ARGS=(-p "$SSH_PORT")
if [ -f "$SSH_KEY" ]; then
    SSH_ARGS+=(-i "$SSH_KEY")
fi

PW_B64=$(printf '%s' "$NEW_PASS" | base64 | tr -d '\r\n')
USER_B64=$(printf '%s' "$PANEL_USER" | base64 | tr -d '\r\n')
unset NEW_PASS

echo "Updating administrator credentials on ${SERVER_IP}..."
if ssh "${SSH_ARGS[@]}" "${SSH_USER}@${SERVER_IP}" "python3 -c \"import base64, subprocess; subprocess.run(['x-ui', 'setting', '-username', base64.b64decode('${USER_B64}').decode(), '-password', base64.b64decode('${PW_B64}').decode()], check=True)\""; then
    echo ""
    echo "Password updated successfully!"
else
    echo ""
    echo "[!] Error: Failed to update administrator password." >&2
    exit 1
fi
