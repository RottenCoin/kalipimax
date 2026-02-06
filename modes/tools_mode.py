#!/usr/bin/env python3
"""
KaliPiMax Tools Mode
Quick tool launcher with running status.
"""

import subprocess
import time
from PIL import Image

from ui.base_mode import MenuMode
from ui.renderer import Canvas
from core.state import state, AlertLevel


# Tool definitions
TOOLS = [
    {
        'name': 'tcpdump',
        'desc': 'Packet capture',
        'start': 'sudo tcpdump -i any -w /tmp/capture.pcap &',
        'stop': 'sudo killall tcpdump',
        'check': 'pgrep tcpdump',
    },
    {
        'name': 'bettercap',
        'desc': 'Network attack',
        'start': 'sudo bettercap -caplet /root/recon.cap &',
        'stop': 'sudo killall bettercap',
        'check': 'pgrep bettercap',
    },
    {
        'name': 'hostapd',
        'desc': 'Access point',
        'start': 'sudo systemctl start hostapd',
        'stop': 'sudo systemctl stop hostapd',
        'check': 'systemctl is-active hostapd --quiet',
    },
    {
        'name': 'dnsmasq',
        'desc': 'DNS/DHCP server',
        'start': 'sudo systemctl start dnsmasq',
        'stop': 'sudo systemctl stop dnsmasq',
        'check': 'systemctl is-active dnsmasq --quiet',
    },
    {
        'name': 'tshark',
        'desc': 'Wireshark CLI',
        'start': 'sudo tshark -i wlan0 -w /tmp/tshark.pcap &',
        'stop': 'sudo killall tshark',
        'check': 'pgrep tshark',
    },
    {
        'name': 'ncat',
        'desc': 'Netcat listener',
        'start': 'ncat -lvnp 4444 &',
        'stop': 'pkill -f "ncat -l"',
        'check': 'pgrep -f "ncat -l"',
    },
    {
        'name': 'ssh',
        'desc': 'SSH server',
        'start': 'sudo systemctl start ssh',
        'stop': 'sudo systemctl stop ssh',
        'check': 'systemctl is-active ssh --quiet',
    },
]


def is_tool_running(tool: dict) -> bool:
    """Check if a tool is currently running."""
    try:
        result = subprocess.run(
            tool['check'],
            shell=True,
            capture_output=True,
            timeout=2
        )
        return result.returncode == 0
    except:
        return False


def start_tool(tool: dict) -> bool:
    """Start a tool."""
    try:
        subprocess.run(
            tool['start'],
            shell=True,
            timeout=10,
            capture_output=True
        )
        time.sleep(0.5)
        return is_tool_running(tool)
    except Exception as e:
        print(f"Failed to start {tool['name']}: {e}")
        return False


def stop_tool(tool: dict) -> bool:
    """Stop a tool."""
    try:
        subprocess.run(
            tool['stop'],
            shell=True,
            timeout=10,
            capture_output=True
        )
        time.sleep(0.5)
        return not is_tool_running(tool)
    except Exception as e:
        print(f"Failed to stop {tool['name']}: {e}")
        return False


class ToolsMode(MenuMode):
    """
    Quick tool launcher mode.
    
    Start/stop common tools with visual status indicators.
    """
    
    def __init__(self):
        super().__init__("TOOLS", "🔧")
        
        self._tool_status = {}
        self._last_refresh = 0
        self._refresh_interval = 3.0
        
        # Build menu items
        self._rebuild_menu()
    
    def _rebuild_menu(self):
        """Rebuild menu items with current status."""
        self._menu_items = []
        
        for tool in TOOLS:
            running = self._tool_status.get(tool['name'], False)
            
            self._menu_items.append({
                'icon': '▶' if not running else '■',
                'text': tool['name'],
                'status': 'RUN' if running else '---',
                'status_colour': 'ok' if running else 'text_dim',
                'action': lambda t=tool: self._toggle_tool(t),
            })
        
        # Refresh menu renderer if exists
        self._refresh_menu()
    
    def _refresh_status(self):
        """Refresh running status of all tools."""
        for tool in TOOLS:
            self._tool_status[tool['name']] = is_tool_running(tool)
        
        self._last_refresh = time.time()
        self._rebuild_menu()
    
    def on_enter(self):
        super().on_enter()
        self._refresh_status()
    
    def _toggle_tool(self, tool: dict):
        """Toggle a tool on/off."""
        running = self._tool_status.get(tool['name'], False)
        
        if running:
            # Stop it
            if stop_tool(tool):
                state.add_alert(f"Stopped: {tool['name']}", AlertLevel.OK)
                self._tool_status[tool['name']] = False
            else:
                state.add_alert(f"Failed to stop: {tool['name']}", AlertLevel.ERROR)
        else:
            # Start it
            if start_tool(tool):
                state.add_alert(f"Started: {tool['name']}", AlertLevel.OK)
                self._tool_status[tool['name']] = True
            else:
                state.add_alert(f"Failed to start: {tool['name']}", AlertLevel.ERROR)
        
        self._rebuild_menu()
        state.render_needed = True
    
    def on_key3(self):
        """Refresh tool status."""
        self._refresh_status()
        state.add_alert("Status refreshed", AlertLevel.INFO)
        state.render_needed = True
    
    def render(self) -> Image.Image:
        # Auto-refresh status periodically
        if time.time() - self._last_refresh > self._refresh_interval:
            self._refresh_status()
        
        canvas = self._create_canvas()
        
        y = self._render_header(canvas)
        
        # Count running tools
        running_count = sum(1 for v in self._tool_status.values() if v)
        canvas.text(80, 2, f"{running_count} running", colour='ok' if running_count else 'text_dim', font='tiny')
        
        # Menu
        self._menu.start_y = y
        self._render_menu(canvas, start_y=y)
        
        # Show description of selected tool
        selected_idx = self._get_selected_index()
        if selected_idx < len(TOOLS):
            desc = TOOLS[selected_idx].get('desc', '')
            canvas.text(2, 115, desc, colour='text_dim', font='tiny')
        
        self._render_footer(canvas, "●:Toggle K3:Refresh")
        
        return canvas.get_image()
