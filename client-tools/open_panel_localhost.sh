#!/usr/bin/env bash
# ==============================================================================
# 3X-UI Localhost Secure Tunnel (macOS / Linux)
# ==============================================================================
set -euo pipefail

SERVER_IP="YOUR_SERVER_IP"
SSH_PORT="22"
SSH_USER="root"
SSH_KEY="$HOME/.ssh/id_ed25519"
PANEL_PORT="23600"
SUB_PORT="2096"
PANEL_PATH="web_secret_path"

echo "========================================================"
echo " Connecting to 3X-UI Panel via Encrypted SSH Tunnel"
echo "========================================================"
echo " Panel URL:        http://localhost:${PANEL_PORT}/${PANEL_PATH}/"
echo " Subscription URL: http://localhost:${SUB_PORT}/sub/<token>"
echo "========================================================"

SSH_ARGS=(
    -p "$SSH_PORT"
    -N
    -o ExitOnForwardFailure=yes
    -o ServerAliveInterval=30
    -L "127.0.0.1:${PANEL_PORT}:127.0.0.1:${PANEL_PORT}"
    -L "127.0.0.1:${SUB_PORT}:127.0.0.1:${SUB_PORT}"
)
if [ -f "$SSH_KEY" ]; then
    SSH_ARGS+=(-i "$SSH_KEY")
fi

PANEL_URL="http://localhost:${PANEL_PORT}/${PANEL_PATH}/"
if command -v xdg-open &> /dev/null; then
    (sleep 2 && xdg-open "$PANEL_URL" >/dev/null 2>&1) &
elif command -v open &> /dev/null; then
    (sleep 2 && open "$PANEL_URL" >/dev/null 2>&1) &
else
    echo "Access URL: $PANEL_URL"
fi

ssh "${SSH_ARGS[@]}" "${SSH_USER}@${SERVER_IP}"
