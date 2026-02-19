#!/usr/bin/env python3
"""
KaliPiMax WiFi Tools Interface Management

Provides helpers for auto-switching wlan1 between managed and monitor modes
depending on which tool is being run and whether tools_on_target is active.

Usage:
    # Network-layer tools (nmap, responder, mitm):
    iface = get_target_interface()  # returns wlan1 if tools mode, else auto-detect

    # Monitor-mode tools (deauth, handshake, airodump):
    iface = prepare_monitor()       # switches wlan1 to monitor, returns iface name
    # ...after tool finishes...
    restore_after_monitor()          # switches wlan1 back to managed+reconnect
"""

import subprocess
from core.state import state, AlertLevel
from config import WIFI_INTERFACE, WIFI_MONITOR_INTERFACE


def get_target_interface() -> str:
    """
    Get the right interface for network-layer tools.

    If tools_on_target: ensures wlan1 is in managed mode and connected,
    returns WIFI_MONITOR_INTERFACE (wlan1).
    Otherwise: returns the default route interface (auto-detected).
    """
    if state.tools_on_target:
        _ensure_managed_connected()
        return WIFI_MONITOR_INTERFACE
    return _get_default_interface()


def prepare_monitor() -> str:
    """
    Prepare wlan1 for monitor-mode tools.
    Switches to monitor mode if not already.

    Returns the monitor interface name (e.g. wlan1mon), or empty string on failure.
    """
    mon_iface = f"{WIFI_MONITOR_INTERFACE}mon"

    # Check if already in monitor
    if _is_monitor(mon_iface):
        return mon_iface

    try:
        subprocess.run(
            f"sudo airmon-ng check kill && sudo airmon-ng start {WIFI_MONITOR_INTERFACE}",
            shell=True, capture_output=True, timeout=15
        )
        if _is_monitor(mon_iface):
            return mon_iface
    except Exception:
        pass

    state.add_alert("Failed: monitor mode", AlertLevel.ERROR)
    return ""


def restore_after_monitor():
    """
    Callback: switch wlan1 back to managed mode after a monitor-mode tool finishes.
    Only reconnects if tools_on_target is active.
    """
    mon_iface = f"{WIFI_MONITOR_INTERFACE}mon"

    try:
        # Stop monitor mode
        subprocess.run(
            f"sudo airmon-ng stop {mon_iface}",
            shell=True, capture_output=True, timeout=10
        )
    except Exception:
        pass

    if state.tools_on_target:
        _ensure_managed_connected()


# -----------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------

def _get_default_interface() -> str:
    """Auto-detect the primary network interface."""
    try:
        result = subprocess.run(
            "ip route | grep default | awk '{print $5}' | head -1",
            shell=True, capture_output=True, text=True, timeout=5
        )
        iface = result.stdout.strip()
        return iface if iface else WIFI_INTERFACE
    except Exception:
        return WIFI_INTERFACE


def _is_monitor(interface: str) -> bool:
    """Check if an interface exists and is in monitor mode."""
    try:
        result = subprocess.run(
            f"iw dev {interface} info",
            shell=True, capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0 and 'monitor' in result.stdout.lower()
    except Exception:
        return False


def _ensure_managed_connected():
    """Ensure wlan1 is in managed mode and connected to the target network."""
    from core import wifi_profiles

    mon_iface = f"{WIFI_MONITOR_INTERFACE}mon"

    # Stop monitor if active
    if _is_monitor(mon_iface):
        try:
            subprocess.run(
                f"sudo airmon-ng stop {mon_iface}",
                shell=True, capture_output=True, timeout=10
            )
        except Exception:
            pass

    # Restart NetworkManager to recover managed mode
    try:
        subprocess.run(
            "sudo systemctl restart NetworkManager",
            shell=True, capture_output=True, timeout=10
        )
    except Exception:
        pass

    # Connect to target network
    ssid = state.target_ssid
    pw = state.target_password
    if not ssid:
        return

    try:
        safe_ssid = ssid.replace("'", "'\\''")
        safe_pw = pw.replace("'", "'\\''")
        result = subprocess.run(
            f"nmcli device wifi connect '{safe_ssid}' "
            f"password '{safe_pw}' ifname {WIFI_MONITOR_INTERFACE}",
            shell=True, capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            state.add_alert(f"wlan1 reconnect failed", AlertLevel.WARNING)
    except Exception:
        state.add_alert(f"wlan1 reconnect error", AlertLevel.WARNING)
