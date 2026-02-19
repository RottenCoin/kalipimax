#!/bin/bash
# KaliPiMax: Fix SSH access over WiFi
# Run as root: sudo bash fix_wifi_ssh.sh

set -e

echo "=== KaliPiMax SSH over WiFi Fix ==="
echo

# 1. Check SSH is running
echo "[1] Checking SSH service..."
if systemctl is-active --quiet ssh; then
    echo "    SSH: RUNNING"
else
    echo "    SSH: NOT RUNNING — starting..."
    systemctl enable ssh
    systemctl start ssh
fi

# 2. Check sshd listen address
echo "[2] Checking sshd bind address..."
LISTEN=$(grep -E "^ListenAddress" /etc/ssh/sshd_config 2>/dev/null || true)
if [ -n "$LISTEN" ]; then
    echo "    FOUND: $LISTEN"
    echo "    Fixing: commenting out ListenAddress to listen on all interfaces..."
    sed -i 's/^ListenAddress/#ListenAddress/' /etc/ssh/sshd_config
    systemctl restart ssh
    echo "    SSH restarted — now listening on all interfaces"
else
    echo "    OK: No ListenAddress restriction (listens on all interfaces)"
fi

# 3. Check firewall
echo "[3] Checking firewall..."
if command -v ufw &>/dev/null; then
    UFW_STATUS=$(ufw status 2>/dev/null | head -1)
    echo "    UFW: $UFW_STATUS"
    if echo "$UFW_STATUS" | grep -q "active"; then
        echo "    Allowing SSH through UFW..."
        ufw allow ssh
    fi
elif command -v iptables &>/dev/null; then
    # Check if there are DROP rules that might block SSH on wlan0
    DROPS=$(iptables -L INPUT -n 2>/dev/null | grep -c "DROP" || true)
    if [ "$DROPS" -gt 0 ]; then
        echo "    WARNING: iptables has $DROPS DROP rules"
        echo "    Adding explicit SSH allow for wlan0..."
        iptables -I INPUT -i wlan0 -p tcp --dport 22 -j ACCEPT
        echo "    Rule added (non-persistent — see below)"
    else
        echo "    OK: No DROP rules found"
    fi
else
    echo "    OK: No firewall detected"
fi

# 4. Check wlan0 has an IP
echo "[4] Checking wlan0 IP address..."
WLAN_IP=$(ip -4 addr show wlan0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || true)
if [ -n "$WLAN_IP" ]; then
    echo "    wlan0 IP: $WLAN_IP"
else
    echo "    WARNING: wlan0 has no IP address"
    echo "    WiFi may not be connected. Use WiFi Connect on the device first."
fi

# 5. Check if SSH port is actually listening on wlan0 IP
echo "[5] Checking SSH is reachable..."
if [ -n "$WLAN_IP" ]; then
    if ss -tlnp | grep -q ":22.*0.0.0.0"; then
        echo "    OK: SSH listening on 0.0.0.0:22 (all interfaces)"
    elif ss -tlnp | grep -q ":22.*$WLAN_IP"; then
        echo "    OK: SSH listening on $WLAN_IP:22"
    else
        echo "    WARNING: SSH may not be listening on wlan0 IP"
        echo "    Current SSH listeners:"
        ss -tlnp | grep ":22" || echo "    (none found!)"
    fi
fi

# 6. Make iptables rule persistent if iptables-persistent is installed
if dpkg -l iptables-persistent &>/dev/null 2>&1; then
    echo "[6] Saving iptables rules..."
    iptables-save > /etc/iptables/rules.v4
    echo "    Saved"
else
    echo "[6] iptables-persistent not installed (rules won't survive reboot)"
    echo "    Install with: apt install iptables-persistent"
fi

echo
echo "=== Summary ==="
if [ -n "$WLAN_IP" ]; then
    echo "Try connecting: ssh kali@$WLAN_IP"
else
    echo "Connect to WiFi first, then re-run this script."
fi
echo
echo "If still failing, check your WiFi router isn't blocking"
echo "client-to-client traffic (AP isolation / client isolation)."
