#!/usr/bin/env python3
"""
KaliPiMax WiFi Mode
Wireless attacks, monitoring, and reconnaissance.
"""

import subprocess
import re
from PIL import Image

from ui.base_mode import MenuMode
from ui.renderer import Canvas
from core.state import state, AlertLevel
from core.payload import payload_runner, get_loot_path
from config import WIFI_MONITOR_INTERFACE, DEAUTH_COUNT, DEAUTH_TIMEOUT


def get_wireless_interfaces() -> list:
    """Get list of wireless interfaces."""
    try:
        result = subprocess.run(
            "iw dev | grep Interface | awk '{print $2}'",
            shell=True, capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip().split('\n') if result.stdout.strip() else []
    except:
        return []


def is_monitor_mode(interface: str) -> bool:
    """Check if interface is in monitor mode."""
    try:
        result = subprocess.run(
            f"iw dev {interface} info",
            shell=True, capture_output=True, text=True, timeout=5
        )
        return 'monitor' in result.stdout.lower()
    except:
        return False


def get_interface_info(interface: str) -> dict:
    """Get interface information."""
    info = {
        'exists': False,
        'mode': 'unknown',
        'channel': 'N/A',
        'mac': 'N/A'
    }
    
    try:
        result = subprocess.run(
            f"iw dev {interface} info",
            shell=True, capture_output=True, text=True, timeout=5
        )
        
        if result.returncode == 0:
            info['exists'] = True
            
            if 'monitor' in result.stdout.lower():
                info['mode'] = 'monitor'
            elif 'managed' in result.stdout.lower():
                info['mode'] = 'managed'
            
            channel_match = re.search(r'channel (\d+)', result.stdout)
            if channel_match:
                info['channel'] = channel_match.group(1)
            
            # Get MAC
            mac_result = subprocess.run(
                f"cat /sys/class/net/{interface}/address",
                shell=True, capture_output=True, text=True, timeout=2
            )
            if mac_result.returncode == 0:
                info['mac'] = mac_result.stdout.strip()[:17]
    except:
        pass
    
    return info


class WiFiMode(MenuMode):
    """
    WiFi attack and monitoring mode.
    
    Actions: Monitor mode toggle, deauth, scanning, packet capture
    """
    
    def __init__(self):
        super().__init__("WIFI", "📡")
        
        self._interface = WIFI_MONITOR_INTERFACE
        self._monitor_iface = f"{WIFI_MONITOR_INTERFACE}mon"
        
        self._menu_items = [
            {'icon': '●', 'text': 'Monitor Mode ON', 'action': self._enable_monitor},
            {'icon': '●', 'text': 'Monitor Mode OFF', 'action': self._disable_monitor},
            {'icon': '●', 'text': 'WiFi Scan', 'action': self._scan_networks},
            {'icon': '●', 'text': 'Deauth Attack', 'action': self._deauth_attack},
            {'icon': '●', 'text': 'Capture Handshake', 'action': self._capture_handshake},
            {'icon': '●', 'text': 'MAC Randomise', 'action': self._randomise_mac},
            {'icon': '●', 'text': 'Interface Info', 'action': self._show_info},
        ]
        
        self._iface_info = {}
    
    def on_enter(self):
        super().on_enter()
        self._refresh_interface_info()
    
    def _refresh_interface_info(self):
        """Refresh interface information."""
        # Check for monitor interface first
        if get_interface_info(self._monitor_iface)['exists']:
            self._iface_info = get_interface_info(self._monitor_iface)
            self._iface_info['name'] = self._monitor_iface
        else:
            self._iface_info = get_interface_info(self._interface)
            self._iface_info['name'] = self._interface
    
    def _enable_monitor(self):
        """Enable monitor mode on wireless interface."""
        payload_runner.run(
            f"sudo airmon-ng check kill && sudo airmon-ng start {self._interface}",
            "Enable Monitor",
            timeout=30,
            on_complete=self._refresh_interface_info
        )
    
    def _disable_monitor(self):
        """Disable monitor mode."""
        payload_runner.run(
            f"sudo airmon-ng stop {self._monitor_iface} && "
            f"sudo systemctl restart NetworkManager",
            "Disable Monitor",
            timeout=30,
            on_complete=self._refresh_interface_info
        )
    
    def _scan_networks(self):
        """Scan for wireless networks."""
        # Determine which interface to use
        iface = self._monitor_iface if self._iface_info.get('mode') == 'monitor' else self._interface
        outfile = get_loot_path("wifi", "scan", "csv")
        
        # Remove extension as airodump adds it
        outfile_base = outfile.replace('.csv', '')
        
        payload_runner.run(
            f"sudo airodump-ng {iface} "
            f"--write {outfile_base} --output-format csv",
            "WiFi Scan",
            timeout=25
        )
    
    def _deauth_attack(self):
        """Broadcast deauth attack."""
        if self._iface_info.get('mode') != 'monitor':
            state.add_alert("Enable monitor mode first!", AlertLevel.ERROR)
            return
        
        iface = self._iface_info.get('name', self._monitor_iface)
        outfile = get_loot_path("deauth", "deauth", "log")
        
        payload_runner.run(
            f"sudo aireplay-ng --deauth {DEAUTH_COUNT} "
            f"-a FF:FF:FF:FF:FF:FF {iface} 2>&1 | tee {outfile}",
            "Deauth Attack",
            timeout=DEAUTH_TIMEOUT + 5
        )
    
    def _capture_handshake(self):
        """Capture WPA handshakes."""
        if self._iface_info.get('mode') != 'monitor':
            state.add_alert("Enable monitor mode first!", AlertLevel.ERROR)
            return
        
        iface = self._iface_info.get('name', self._monitor_iface)
        outfile = get_loot_path("wifi", "handshake", "cap")
        outfile_base = outfile.replace('.cap', '')
        
        payload_runner.run(
            f"sudo airodump-ng {iface} "
            f"--write {outfile_base} --output-format pcap",
            "Capture Handshake",
            timeout=65
        )
    
    def _randomise_mac(self):
        """Randomise MAC address."""
        iface = self._interface
        
        payload_runner.run(
            f"sudo ip link set {iface} down && "
            f"sudo macchanger -r {iface} && "
            f"sudo ip link set {iface} up",
            "MAC Randomise",
            timeout=10,
            on_complete=self._refresh_interface_info
        )
    
    def _show_info(self):
        """Show current interface information."""
        self._refresh_interface_info()
        info = self._iface_info
        state.add_alert(
            f"{info.get('name', 'N/A')}: {info.get('mode', 'N/A')}",
            AlertLevel.INFO
        )
    
    def render(self) -> Image.Image:
        canvas = self._create_canvas()
        
        y = self._render_header(canvas, "WIFI ATTACK")
        
        # Show interface status
        info = self._iface_info
        iface_name = info.get('name', 'N/A')
        mode = info.get('mode', 'unknown')
        
        mode_colour = 'ok' if mode == 'monitor' else 'warning' if mode == 'managed' else 'error'
        canvas.text(2, y, f"{iface_name}: ", colour='text_dim', font='tiny')
        canvas.text(55, y, mode.upper(), colour=mode_colour, font='tiny')
        y += 10
        
        # Menu
        self._menu.start_y = y
        self._render_menu(canvas, start_y=y)
        
        self._render_footer(canvas, "K3:Refresh/Cancel")
        
        return canvas.get_image()
    
    def on_key3(self):
        """Cancel payload or refresh interface info."""
        if state.is_payload_running():
            payload_runner.cancel()
        else:
            self._refresh_interface_info()
            state.render_needed = True
