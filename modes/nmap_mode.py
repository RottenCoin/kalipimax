#!/usr/bin/env python3
"""
KaliPiMax Nmap Mode
Network reconnaissance and port scanning.
"""

import subprocess
from PIL import Image

from ui.base_mode import MenuMode
from ui.renderer import Canvas
from core.state import state, AlertLevel
from core.payload import payload_runner, get_loot_path
from core.wifi_tools import get_target_interface
from config import NMAP_TIMING


def get_network_cidr(interface: str = None) -> str:
    """Auto-detect current network CIDR, optionally for a specific interface."""
    try:
        if interface:
            cmd = (
                f"ip -4 addr show {interface} | "
                f"grep -oP '(?<=inet\\s)\\d+(\\.\\d+){{3}}/\\d+' | head -1"
            )
        else:
            cmd = (
                "ip -4 addr show | grep -oP '(?<=inet\\s)\\d+(\\.\\d+){3}/\\d+' | "
                "grep -v '127.0.0.1' | head -1"
            )
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=5
        )
        cidr = result.stdout.strip()
        if cidr:
            return cidr
    except:
        pass
    return "192.168.1.0/24"


class NmapMode(MenuMode):
    """
    Nmap network reconnaissance mode.
    
    Provides various scan types with auto-detected network targeting.
    Results saved to loot directory.
    """
    
    def __init__(self):
        super().__init__("NMAP", "🔍")
        
        self._menu_items = [
            {'icon': '●', 'text': 'Quick Scan', 'action': self._quick_scan},
            {'icon': '●', 'text': 'Full Port Scan', 'action': self._full_scan},
            {'icon': '●', 'text': 'Service Scan', 'action': self._service_scan},
            {'icon': '●', 'text': 'Vuln Scan', 'action': self._vuln_scan},
            {'icon': '●', 'text': 'OS Detection', 'action': self._os_scan},
            {'icon': '●', 'text': 'Stealth SYN', 'action': self._stealth_scan},
            {'icon': '●', 'text': 'UDP Scan', 'action': self._udp_scan},
            {'icon': '📄', 'text': 'View Loot', 'action': self._view_loot},
        ]
        
        self._current_network = None
        self._attack_iface = None
    
    def on_enter(self):
        super().on_enter()
        self._refresh_target()
    
    def _refresh_target(self):
        """Refresh target network and interface."""
        if state.tools_on_target:
            self._attack_iface = get_target_interface()
            self._current_network = get_network_cidr(self._attack_iface)
        else:
            self._attack_iface = None
            self._current_network = get_network_cidr()
    
    def _iface_flag(self) -> str:
        """Return nmap -e flag if using a specific attack interface."""
        if self._attack_iface:
            return f"-e {self._attack_iface} "
        return ""
    
    def _quick_scan(self):
        """Fast scan of common ports."""
        net = self._current_network
        outfile = get_loot_path("nmap", "quick")
        
        payload_runner.run(
            f"nmap {self._iface_flag()}{NMAP_TIMING} -F {net} -oN {outfile}",
            "Quick Scan",
            timeout=180
        )
    
    def _full_scan(self):
        """Scan all 65535 ports."""
        net = self._current_network
        outfile = get_loot_path("nmap", "full")
        
        payload_runner.run(
            f"nmap {self._iface_flag()}-p- {net} -oN {outfile}",
            "Full Port Scan",
            timeout=600
        )
    
    def _service_scan(self):
        """Service version detection."""
        net = self._current_network
        outfile = get_loot_path("nmap", "service")
        
        payload_runner.run(
            f"nmap {self._iface_flag()}-sV -sC {net} -oN {outfile}",
            "Service Scan",
            timeout=300
        )
    
    def _vuln_scan(self):
        """Vulnerability scanning with NSE scripts."""
        net = self._current_network
        outfile = get_loot_path("nmap", "vuln")
        
        payload_runner.run(
            f"nmap {self._iface_flag()}--script vuln {net} -oN {outfile}",
            "Vuln Scan",
            timeout=600
        )
    
    def _os_scan(self):
        """OS detection scan (requires root)."""
        net = self._current_network
        outfile = get_loot_path("nmap", "os")
        
        payload_runner.run(
            f"sudo nmap {self._iface_flag()}-O {net} -oN {outfile}",
            "OS Detection",
            timeout=300
        )
    
    def _stealth_scan(self):
        """Stealthy SYN scan with slower timing."""
        net = self._current_network
        outfile = get_loot_path("nmap", "stealth")
        
        payload_runner.run(
            f"sudo nmap {self._iface_flag()}-sS -T2 {net} -oN {outfile}",
            "Stealth Scan",
            timeout=600
        )
    
    def _udp_scan(self):
        """UDP port scan (requires root)."""
        net = self._current_network
        outfile = get_loot_path("nmap", "udp")
        
        payload_runner.run(
            f"sudo nmap {self._iface_flag()}-sU --top-ports 100 {net} -oN {outfile}",
            "UDP Scan",
            timeout=600
        )
    
    def _view_loot(self):
        """Show loot directory location."""
        state.add_alert("Loot: ~/kalipimax/loot/nmap/", AlertLevel.INFO)
    
    def render(self) -> Image.Image:
        canvas = self._create_canvas()
        
        y = self._render_header(canvas, "NMAP RECON")
        
        # Show current target network
        canvas.text(2, y, f"Target: {self._current_network}", colour='info', font='tiny')
        if self._attack_iface:
            canvas.text(90, y, self._attack_iface, colour='ok', font='tiny')
        y += 10
        
        # Menu
        self._menu.start_y = y
        self._render_menu(canvas, start_y=y)
        
        self._render_footer(canvas, "K3:Cancel")
        
        return canvas.get_image()
    
    def on_key3(self):
        """Cancel running scan or refresh network."""
        if state.is_payload_running():
            payload_runner.cancel()
        else:
            self._refresh_target()
            state.add_alert(f"Network: {self._current_network}", AlertLevel.INFO)
            state.render_needed = True
