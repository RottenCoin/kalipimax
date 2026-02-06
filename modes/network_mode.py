#!/usr/bin/env python3
"""
KaliPiMax Network Mode
Network interface statistics and connectivity status.
"""

import subprocess
import re
import time
import psutil
from PIL import Image

from ui.base_mode import InfoMode
from ui.renderer import Canvas
from core.state import state, AlertLevel


def format_bytes(b: int) -> str:
    """Format bytes to human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if b < 1024:
            return f"{b:.1f}{unit}"
        b /= 1024
    return f"{b:.1f}TB"


def get_gateway() -> str:
    """Get default gateway IP."""
    try:
        result = subprocess.run(
            "ip route | grep default | awk '{print $3}'",
            shell=True, capture_output=True, text=True, timeout=2
        )
        return result.stdout.strip() or "N/A"
    except:
        return "N/A"


def get_dns_servers() -> list:
    """Get DNS server IPs."""
    try:
        with open('/etc/resolv.conf', 'r') as f:
            content = f.read()
        servers = re.findall(r'nameserver\s+(\d+\.\d+\.\d+\.\d+)', content)
        return servers[:2]  # Return first 2
    except:
        return []


class NetworkMode(InfoMode):
    """
    Network interface statistics mode.
    
    Shows: Interface status, TX/RX bytes, gateway, DNS
    """
    
    def __init__(self):
        super().__init__("NETWORK", "🌐")
        self._refresh_interval = 2.0
    
    def _refresh_data(self):
        """Refresh network statistics."""
        super()._refresh_data()
        
        self._cached_data = {
            'interfaces': {},
            'gateway': get_gateway(),
            'dns': get_dns_servers(),
        }
        
        # Get interface stats
        net_io = psutil.net_io_counters(pernic=True)
        net_if = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()
        
        for iface in ['eth0', 'wlan0', 'usb0']:
            if iface in net_io:
                stats = net_io[iface]
                is_up = net_if.get(iface, {}).isup if iface in net_if else False
                
                # Get IP address
                ip = "N/A"
                if iface in addrs:
                    for addr in addrs[iface]:
                        if addr.family.name == 'AF_INET':
                            ip = addr.address
                            break
                
                self._cached_data['interfaces'][iface] = {
                    'up': is_up,
                    'ip': ip,
                    'tx': stats.bytes_sent,
                    'rx': stats.bytes_recv,
                }
    
    def render(self) -> Image.Image:
        canvas = self._create_canvas()
        
        # Auto-refresh
        if self._should_refresh():
            self._refresh_data()
        
        y = self._render_header(canvas)
        
        data = self._cached_data
        
        # Interfaces
        for iface, info in data.get('interfaces', {}).items():
            # Interface name and status
            status_colour = 'ok' if info['up'] else 'error'
            status_char = "▲" if info['up'] else "▼"
            
            canvas.text(2, y, f"{iface}:", colour='info', font='small')
            canvas.text(50, y, status_char, colour=status_colour, font='small')
            canvas.text(60, y, info['ip'][:15], colour='text', font='tiny')
            y += 11
            
            # TX/RX
            canvas.text(10, y, f"↑{format_bytes(info['tx'])}", colour='text_dim', font='tiny')
            canvas.text(65, y, f"↓{format_bytes(info['rx'])}", colour='text_dim', font='tiny')
            y += 11
        
        y += 2
        
        # Gateway
        canvas.text(2, y, f"GW: {data.get('gateway', 'N/A')}", colour='highlight', font='small')
        y += 11
        
        # DNS
        dns_list = data.get('dns', [])
        if dns_list:
            canvas.text(2, y, f"DNS: {dns_list[0]}", colour='text_dim', font='tiny')
            y += 9
            if len(dns_list) > 1:
                canvas.text(2, y, f"     {dns_list[1]}", colour='text_dim', font='tiny')
        
        self._render_footer(canvas, "K3:Refresh")
        
        return canvas.get_image()
