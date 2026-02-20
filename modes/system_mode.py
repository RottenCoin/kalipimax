#!/usr/bin/env python3
"""
KaliPiMax System Mode
System monitoring, reboot, shutdown, kill all tools.
"""

import os
import socket
import psutil
from PIL import Image

from ui.base_mode import MenuMode
from ui.renderer import Canvas, get_colour_for_percent
from core.state import state, AlertLevel
from core.payload import payload_runner
from config import CONFIRM_TIMEOUT, BASE_DIR


def get_cpu_temp() -> float:
    """Get CPU temperature in Celsius."""
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            return float(f.read().strip()) / 1000.0
    except:
        return 0.0


def get_local_ip() -> str:
    """Get local IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "No network"


class SystemMode(MenuMode):
    """
    System status and control mode.
    
    Shows: CPU usage, RAM usage, temperature, IP address
    Actions: Reboot, Shutdown, Kill All Tools
    """
    
    def __init__(self):
        super().__init__("SYSTEM", "⚙")
        self._updating = False
        
        self._menu_items = [
            {'icon': '⟳', 'text': 'Reboot', 'action': self._reboot},
            {'icon': '⏻', 'text': 'Shutdown', 'action': self._shutdown},
            {'icon': '✕', 'text': 'Kill All Tools', 'action': self._kill_all},
            {'icon': '↓', 'text': 'Update&Relaunch', 'action': self._update_and_reboot},
        ]
    
    def _reboot(self):
        """Reboot with confirmation."""
        if state.request_confirm("reboot", CONFIRM_TIMEOUT):
            state.add_alert("Rebooting...", AlertLevel.WARNING)
            os.system("sudo reboot")
        else:
            state.add_alert("Press again to reboot", AlertLevel.WARNING)
    
    def _shutdown(self):
        """Shutdown with confirmation."""
        if state.request_confirm("shutdown", CONFIRM_TIMEOUT):
            state.add_alert("Shutting down...", AlertLevel.WARNING)
            os.system("sudo shutdown -h now")
        else:
            state.add_alert("Press again to shutdown", AlertLevel.WARNING)
    
    def _kill_all(self):
        """Kill all offensive tools."""
        payload_runner.kill_all_tools()
    
    def _update_and_reboot(self):
        """Git pull from main branch, then reboot."""
        if state.request_confirm("update", CONFIRM_TIMEOUT):
            self._updating = True
            state.render_needed = True
            repo_dir = str(BASE_DIR)
            cmd = (
                f"cd {repo_dir} && "
                f"timeout 120 git fetch origin main && "
                f"git reset --hard origin/main && "
                f"sudo reboot"
            )
            payload_runner.run(cmd, "Update&Relaunch", timeout=150)
        else:
            state.add_alert("Press again to update", AlertLevel.WARNING)
    
    def render(self) -> Image.Image:
        canvas = self._create_canvas()
        
        if getattr(self, '_updating', False):
            canvas.text(18, 30, "UPDATING", colour='warning', font='title')
            canvas.text(30, 55, "WAIT!", colour='error', font='title')
            canvas.text(10, 85, "Do not power off", colour='text_dim', font='small')
            return canvas.get_image()
        
        y = self._render_header(canvas)
        
        # Get system stats
        cpu_percent = psutil.cpu_percent(interval=0)
        mem = psutil.virtual_memory()
        temp = get_cpu_temp()
        ip = get_local_ip()
        
        # CPU with bar
        cpu_colour = get_colour_for_percent(cpu_percent)
        canvas.text(2, y, f"CPU {cpu_percent:5.1f}%", colour=cpu_colour, font='medium')
        
        temp_colour = get_colour_for_percent(temp, thresholds=(60, 70))
        canvas.text(78, y, f"{temp:.0f}°C", colour=temp_colour, font='medium')
        y += 12
        
        canvas.progress_bar(2, y, 124, 4, cpu_percent, fill_colour=cpu_colour)
        y += 8
        
        # RAM with bar
        mem_colour = get_colour_for_percent(mem.percent)
        mem_used_mb = mem.used // (1024 * 1024)
        canvas.text(2, y, f"RAM {mem.percent:5.1f}%", colour='info', font='medium')
        canvas.text(78, y, f"{mem_used_mb}M", colour='text_dim', font='small')
        y += 12
        
        canvas.progress_bar(2, y, 124, 4, mem.percent, fill_colour='bar_mem')
        y += 8
        
        # IP Address
        canvas.text(2, y, f"IP: {ip}", colour='ok', font='small')
        y += 12
        
        # Separator
        canvas.line(2, y, 126, y, colour='text_dim')
        y += 4
        
        # Menu
        self._menu.start_y = y
        self._render_menu(canvas, start_y=y)
        
        self._render_footer(canvas, "K3:Cancel payload")
        
        return canvas.get_image()
    
    def on_key3(self):
        """Cancel running payload."""
        if state.is_payload_running():
            payload_runner.cancel()
        else:
            state.add_alert("No payload running", AlertLevel.INFO)
