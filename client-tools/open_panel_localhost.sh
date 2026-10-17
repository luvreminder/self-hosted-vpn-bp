#!/usr/bin/env bash
# ==============================================================================
# 3X-UI Localhost Secure Tunnel (macOS / Linux)
# ==============================================================================
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

if [ -f "$SSH_KEY" ]; then
    KEY_OPT="-i $SSH_KEY"
else
    KEY_OPT=""
fi

# Launch browser on macOS or Linux
if command -v xdg-open &> /dev/null; then
    xdg-open "http://localhost:${PANEL_PORT}/${PANEL_PATH}/" &
elif command -v open &> /dev/null; then
    open "http://localhost:${PANEL_PORT}/${PANEL_PATH}/" &
else
    echo "Access URL: http://localhost:${PANEL_PORT}/${PANEL_PATH}/"
fi

ssh $KEY_OPT -p "$SSH_PORT" -N \
    -L "${PANEL_PORT}:127.0.0.1:${PANEL_PORT}" \
    -L "${SUB_PORT}:127.0.0.1:${SUB_PORT}" \
    "${SSH_USER}@${SERVER_IP}"
