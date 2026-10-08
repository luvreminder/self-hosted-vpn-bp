#!/usr/bin/env bash
# ==============================================================================
# 3X-UI Administrator Password Reset (macOS / Linux)
# ==============================================================================
SERVER_IP="YOUR_SERVER_IP"
SSH_PORT="22"
SSH_USER="root"
SSH_KEY="$HOME/.ssh/id_ed25519"

echo "========================================================"
echo " 3X-UI Administrator Password Reset Tool (macOS / Linux)"
echo "========================================================"
echo ""

if [ -n "$1" ]; then
    NEW_PASS="$1"
else
    read -r -s -p "Enter new administrator password: " NEW_PASS
    echo ""
fi

if [ -z "$NEW_PASS" ]; then
    echo "[!] Error: Password cannot be empty."
    exit 1
fi

if [ -f "$SSH_KEY" ]; then
    KEY_OPT="-i $SSH_KEY"
else
    KEY_OPT=""
fi

echo "Updating administrator credentials on ${SERVER_IP}..."
ssh $KEY_OPT -p "$SSH_PORT" "${SSH_USER}@${SERVER_IP}" "x-ui setting -username admin -password '$NEW_PASS'"

echo ""
echo "Password updated successfully!"
