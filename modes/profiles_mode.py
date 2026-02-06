#!/usr/bin/env python3
"""
KaliPiMax Profiles Mode
Mission profiles - pre-configured action sets for different scenarios.
"""

import subprocess
import threading
import os
from PIL import Image

from ui.base_mode import MenuMode
from ui.renderer import Canvas
from core.state import state, AlertLevel


# Mission profile definitions
PROFILES = [
    {
        'name': 'Stealth',
        'desc': 'Silent - radio off, min services',
        'icon': '🔇',
        'actions': [
            {'type': 'rfkill', 'device': 'wifi', 'action': 'block'},
            {'type': 'rfkill', 'device': 'bluetooth', 'action': 'block'},
            {'type': 'service', 'name': 'bluetooth', 'action': 'stop'},
            {'type': 'led', 'state': 'off'},
        ]
    },
    {
        'name': 'Network',
        'desc': 'Full connectivity enabled',
        'icon': '🌐',
        'actions': [
            {'type': 'rfkill', 'device': 'all', 'action': 'unblock'},
            {'type': 'service', 'name': 'NetworkManager', 'action': 'start'},
            {'type': 'service', 'name': 'ssh', 'action': 'start'},
        ]
    },
    {
        'name': 'Recon',
        'desc': 'Monitor mode + scanning',
        'icon': '🔍',
        'actions': [
            {'type': 'rfkill', 'device': 'wifi', 'action': 'unblock'},
            {'type': 'exec', 'cmd': 'airmon-ng start wlan1'},
        ]
    },
    {
        'name': 'USB-Eth',
        'desc': 'USB Ethernet gadget mode',
        'icon': '🔌',
        'actions': [
            {'type': 'exec', 'cmd': 'modprobe g_ether'},
            {'type': 'exec', 'cmd': 'ip link set usb0 up'},
            {'type': 'exec', 'cmd': 'ip addr add 192.168.7.2/24 dev usb0'},
        ]
    },
    {
        'name': 'AP Mode',
        'desc': 'Start access point',
        'icon': '📡',
        'actions': [
            {'type': 'service', 'name': 'hostapd', 'action': 'start'},
            {'type': 'service', 'name': 'dnsmasq', 'action': 'start'},
        ]
    },
    {
        'name': 'Low Power',
        'desc': 'Minimum power consumption',
        'icon': '🔋',
        'actions': [
            {'type': 'rfkill', 'device': 'all', 'action': 'block'},
            {'type': 'service', 'name': 'bluetooth', 'action': 'stop'},
            {'type': 'led', 'state': 'off'},
            {'type': 'cpu', 'governor': 'powersave'},
        ]
    },
    {
        'name': 'Performance',
        'desc': 'Maximum performance',
        'icon': '⚡',
        'actions': [
            {'type': 'cpu', 'governor': 'performance'},
        ]
    },
    {
        'name': 'Kill All',
        'desc': 'Stop all tools and services',
        'icon': '🛑',
        'actions': [
            {'type': 'exec', 'cmd': 'pkill -9 tcpdump bettercap nmap responder airmon-ng'},
            {'type': 'service', 'name': 'hostapd', 'action': 'stop'},
            {'type': 'exec', 'cmd': 'airmon-ng stop wlan1mon 2>/dev/null'},
        ]
    },
]


def execute_action(action: dict) -> bool:
    """Execute a single profile action."""
    try:
        action_type = action.get('type')
        
        if action_type == 'service':
            cmd = ['sudo', 'systemctl', action['action'], action['name']]
            subprocess.run(cmd, timeout=10, capture_output=True)
            
        elif action_type == 'rfkill':
            cmd = ['sudo', 'rfkill', action['action'], action['device']]
            subprocess.run(cmd, timeout=5, capture_output=True)
            
        elif action_type == 'exec':
            subprocess.run(
                f"sudo {action['cmd']}",
                shell=True, timeout=30, capture_output=True
            )
            
        elif action_type == 'led':
            if action['state'] == 'off':
                try:
                    with open('/sys/class/leds/ACT/brightness', 'w') as f:
                        f.write('0')
                except:
                    pass
                    
        elif action_type == 'cpu':
            governor = action.get('governor')
            if governor:
                for cpu in range(4):
                    path = f'/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor'
                    if os.path.exists(path):
                        try:
                            with open(path, 'w') as f:
                                f.write(governor)
                        except PermissionError:
                            subprocess.run(
                                f"echo {governor} | sudo tee {path}",
                                shell=True, capture_output=True
                            )
        
        return True
        
    except Exception as e:
        print(f"Profile action failed: {e}")
        return False


class ProfilesMode(MenuMode):
    """
    Mission profiles mode.
    
    Execute pre-configured action sets for different operational scenarios.
    """
    
    def __init__(self):
        super().__init__("PROFILES", "📋")
        
        self._executing = False
        self._current_profile = None
        
        # Build menu items from profiles
        self._menu_items = []
        for profile in PROFILES:
            self._menu_items.append({
                'icon': profile.get('icon', '●'),
                'text': profile['name'],
                'action': lambda p=profile: self._execute_profile(p),
            })
    
    def _execute_profile(self, profile: dict):
        """Execute a profile's actions in background thread."""
        if self._executing:
            state.add_alert("Profile already executing", AlertLevel.WARNING)
            return
        
        self._executing = True
        self._current_profile = profile['name']
        state.render_needed = True
        
        def runner():
            state.add_alert(f"Running: {profile['name']}", AlertLevel.INFO)
            
            success_count = 0
            total_actions = len(profile['actions'])
            
            for action in profile['actions']:
                if execute_action(action):
                    success_count += 1
            
            if success_count == total_actions:
                state.add_alert(f"✓ {profile['name']} complete", AlertLevel.OK)
            else:
                state.add_alert(
                    f"⚠ {profile['name']}: {success_count}/{total_actions}",
                    AlertLevel.WARNING
                )
            
            self._executing = False
            self._current_profile = None
            state.render_needed = True
        
        threading.Thread(target=runner, daemon=True).start()
    
    def render(self) -> Image.Image:
        canvas = self._create_canvas()
        
        y = self._render_header(canvas, "MISSION PROFILE")
        
        # Show execution status
        if self._executing:
            canvas.text(2, y, f"Executing: {self._current_profile}", colour='highlight', font='small')
            y += 12
        
        # Menu
        self._menu.start_y = y
        self._render_menu(canvas, start_y=y)
        
        # Show description of selected profile
        selected_idx = self._get_selected_index()
        if selected_idx < len(PROFILES):
            desc = PROFILES[selected_idx].get('desc', '')
            canvas.text(2, 115, desc[:22], colour='text_dim', font='tiny')
        
        return canvas.get_image()
