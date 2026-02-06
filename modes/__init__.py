#!/usr/bin/env python3
"""
KaliPiMax Modes Package
All operational modes for the LCD interface.
"""

from modes.system_mode import SystemMode
from modes.network_mode import NetworkMode
from modes.nmap_mode import NmapMode
from modes.wifi_mode import WiFiMode
from modes.responder_mode import ResponderMode
from modes.mitm_mode import MITMMode
from modes.shells_mode import ShellsMode
from modes.usb_mode import USBMode
from modes.processes_mode import ProcessesMode
from modes.loot_mode import LootMode
from modes.profiles_mode import ProfilesMode
from modes.tools_mode import ToolsMode
from modes.alerts_mode import AlertsMode


def get_all_modes() -> list:
    """
    Get instances of all operational modes in display order.
    
    Returns:
        List of mode instances.
    """
    return [
        SystemMode(),      # 0: System status and control
        NetworkMode(),     # 1: Network interface info
        NmapMode(),        # 2: Network scanning
        WiFiMode(),        # 3: Wireless attacks
        ResponderMode(),   # 4: Credential capture
        MITMMode(),        # 5: Man-in-the-middle
        ShellsMode(),      # 6: Reverse shell listeners
        USBMode(),         # 7: USB HID attacks
        ProcessesMode(),   # 8: Process management
        LootMode(),        # 9: Captured data browser
        ProfilesMode(),    # 10: Mission profiles
        ToolsMode(),       # 11: Tool launcher
        AlertsMode(),      # 12: System alerts
    ]


__all__ = [
    'SystemMode',
    'NetworkMode', 
    'NmapMode',
    'WiFiMode',
    'ResponderMode',
    'MITMMode',
    'ShellsMode',
    'USBMode',
    'ProcessesMode',
    'LootMode',
    'ProfilesMode',
    'ToolsMode',
    'AlertsMode',
    'get_all_modes',
]
