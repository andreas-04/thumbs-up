#!/usr/bin/env bash
#
# WiFi fallback script
# Waits for wpa_supplicant to associate with a known network.
# If association fails, switches wlan0 into Access Point mode
# using hostapd and dnsmasq.
#
# Installed to: /usr/local/bin/wifi-check.sh
# Managed by:   wifi-fallback.service

set -euo pipefail

IFACE="wlan0"
AP_IP="192.168.4.1"
WAIT_SECONDS=10

echo "wifi-check: waiting ${WAIT_SECONDS}s for wpa_supplicant to associate..."
sleep "$WAIT_SECONDS"

# Check whether wpa_supplicant has completed association
if wpa_cli -i "$IFACE" status 2>/dev/null | grep -q "wpa_state=COMPLETED"; then
    echo "wifi-check: connected to WiFi network — no fallback needed."
    exit 0
fi

echo "wifi-check: no WiFi association detected — switching to Access Point mode."

# Stop wpa_supplicant so it does not fight with hostapd over the interface
systemctl stop wpa_supplicant 2>/dev/null || true
# Kill only the wpa_supplicant instance for our interface (not all interfaces)
pkill -f "wpa_supplicant.*-i${IFACE}" 2>/dev/null || true

# Bring the interface up and assign the static AP address
ip link set "$IFACE" up
ip addr flush dev "$IFACE"
ip addr add "${AP_IP}/24" dev "$IFACE"

# Start hostapd and dnsmasq
systemctl start hostapd
systemctl start dnsmasq

echo "wifi-check: Access Point is up."
echo "  SSID and password are defined in /etc/hostapd/hostapd.conf"
echo "  DHCP range: 192.168.4.10 – 192.168.4.50 (gateway ${AP_IP})"
