#!/usr/bin/env python3
"""
KaliPiMax WiFi Mode
Wireless attacks, monitoring, reconnaissance, and WiFi connectivity.
"""

import subprocess
import re
import threading
from PIL import Image

from ui.base_mode import MenuMode
from ui.renderer import Canvas
from ui.keyboard import OnScreenKeyboard
from core.state import state, AlertLevel
from core.payload import payload_runner, get_loot_path
from config import (
    WIFI_INTERFACE, WIFI_MONITOR_INTERFACE,
    DEAUTH_COUNT, DEAUTH_TIMEOUT, DISPLAY_HEIGHT
)


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


def scan_wifi_networks() -> list:
    """Scan for WiFi networks using nmcli on wlan0. Returns sorted list."""
    try:
        result = subprocess.run(
            f"nmcli -t -f SSID,SIGNAL,SECURITY device wifi list "
            f"ifname {WIFI_INTERFACE} --rescan yes",
            shell=True, capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            return []

        networks = []
        seen = set()
        for line in result.stdout.strip().splitlines():
            parts = line.split(':')
            if len(parts) < 3:
                continue
            ssid = parts[0].strip()
            if not ssid or ssid in seen:
                continue
            seen.add(ssid)
            try:
                signal = int(parts[1])
            except ValueError:
                signal = 0
            security = parts[2].strip() if parts[2].strip() else "Open"
            networks.append({
                'ssid': ssid,
                'signal': signal,
                'security': security,
            })

        # Sort by signal strength, strongest first
        networks.sort(key=lambda n: n['signal'], reverse=True)
        return networks
    except Exception:
        return []


class WiFiMode(MenuMode):
    """
    WiFi attack and monitoring mode.
    
    Actions: Monitor mode toggle, deauth, scanning, packet capture,
             WiFi Connect (scan, select, enter password, connect).
    """
    
    # Connect sub-mode states
    _ST_NONE = None
    _ST_SCANNING = 'scanning'
    _ST_NETWORKS = 'networks'
    _ST_PASSWORD = 'password'
    _ST_CONNECTING = 'connecting'
    
    _NET_VISIBLE = 8   # Network list items visible at once
    
    def __init__(self):
        super().__init__("WIFI", "📡")
        
        self._interface = WIFI_MONITOR_INTERFACE
        self._monitor_iface = f"{WIFI_MONITOR_INTERFACE}mon"
        
        self._menu_items = [
            {'icon': '●', 'text': 'WiFi Connect', 'action': self._start_connect},
            {'icon': '●', 'text': 'Monitor Mode ON', 'action': self._enable_monitor},
            {'icon': '●', 'text': 'Monitor Mode OFF', 'action': self._disable_monitor},
            {'icon': '●', 'text': 'WiFi Scan', 'action': self._scan_networks},
            {'icon': '●', 'text': 'Deauth Attack', 'action': self._deauth_attack},
            {'icon': '●', 'text': 'Capture Handshake', 'action': self._capture_handshake},
            {'icon': '●', 'text': 'MAC Randomise', 'action': self._randomise_mac},
            {'icon': '●', 'text': 'Interface Info', 'action': self._show_info},
        ]
        
        self._iface_info = {}
        
        # Connect sub-mode state
        self._connect_state = self._ST_NONE
        self._networks = []
        self._net_selected = 0
        self._net_scroll = 0
        self._selected_ssid = ""
        self._keyboard = None
    
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
    
    # -----------------------------------------------------------------
    # Normal WiFi attack actions (unchanged)
    # -----------------------------------------------------------------
    
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
        """Scan for wireless networks (airodump)."""
        iface = self._monitor_iface if self._iface_info.get('mode') == 'monitor' else self._interface
        outfile = get_loot_path("wifi", "scan", "csv")
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
    
    # -----------------------------------------------------------------
    # WiFi Connect sub-mode
    # -----------------------------------------------------------------
    
    def _start_connect(self):
        """Begin the WiFi Connect flow — scan for networks."""
        self._connect_state = self._ST_SCANNING
        self._networks = []
        state.render_needed = True
        
        def _do_scan():
            nets = scan_wifi_networks()
            self._networks = nets
            if nets:
                self._connect_state = self._ST_NETWORKS
                self._net_selected = 0
                self._net_scroll = 0
            else:
                state.add_alert("No networks found", AlertLevel.WARNING)
                self._connect_state = self._ST_NONE
            state.render_needed = True
        
        threading.Thread(target=_do_scan, daemon=True).start()
    
    def _select_network(self):
        """User selected a network — open keyboard for password."""
        if not self._networks or self._net_selected >= len(self._networks):
            return
        net = self._networks[self._net_selected]
        self._selected_ssid = net['ssid']
        self._keyboard = OnScreenKeyboard(max_length=63)
        self._connect_state = self._ST_PASSWORD
        state.render_needed = True
    
    def _do_connect(self):
        """Attempt to connect with entered password."""
        password = self._keyboard.text
        ssid = self._selected_ssid
        self._connect_state = self._ST_CONNECTING
        state.render_needed = True
        
        def _run_connect():
            try:
                # Escape single quotes in SSID and password for shell
                safe_ssid = ssid.replace("'", "'\\''")
                safe_pw = password.replace("'", "'\\''")
                
                cmd = (
                    f"nmcli device wifi connect '{safe_ssid}' "
                    f"password '{safe_pw}' ifname {WIFI_INTERFACE}"
                )
                result = subprocess.run(
                    cmd, shell=True, capture_output=True,
                    text=True, timeout=30
                )
                
                if result.returncode == 0:
                    state.add_alert(f"Connected: {ssid[:18]}", AlertLevel.OK)
                else:
                    err = result.stderr.strip()[:30] or "Failed"
                    state.add_alert(f"WiFi: {err}", AlertLevel.ERROR)
            except subprocess.TimeoutExpired:
                state.add_alert("WiFi: connection timeout", AlertLevel.ERROR)
            except Exception as e:
                state.add_alert(f"WiFi: {str(e)[:25]}", AlertLevel.ERROR)
            finally:
                self._connect_state = self._ST_NONE
                state.render_needed = True
        
        threading.Thread(target=_run_connect, daemon=True).start()
    
    def _cancel_connect(self):
        """Cancel any connect sub-mode and return to menu."""
        self._connect_state = self._ST_NONE
        self._keyboard = None
        state.render_needed = True
    
    # -----------------------------------------------------------------
    # Button handlers — delegate to connect sub-mode when active
    # -----------------------------------------------------------------
    
    def on_up(self):
        if self._connect_state == self._ST_NETWORKS:
            if self._net_selected > 0:
                self._net_selected -= 1
                if self._net_selected < self._net_scroll:
                    self._net_scroll = self._net_selected
                state.render_needed = True
        elif self._connect_state == self._ST_PASSWORD:
            self._keyboard.move(0, -1)
            state.render_needed = True
        else:
            super().on_up()
    
    def on_down(self):
        if self._connect_state == self._ST_NETWORKS:
            if self._net_selected < len(self._networks) - 1:
                self._net_selected += 1
                if self._net_selected >= self._net_scroll + self._NET_VISIBLE:
                    self._net_scroll = self._net_selected - self._NET_VISIBLE + 1
                state.render_needed = True
        elif self._connect_state == self._ST_PASSWORD:
            self._keyboard.move(0, 1)
            state.render_needed = True
        else:
            super().on_down()
    
    def on_left(self):
        if self._connect_state == self._ST_PASSWORD:
            self._keyboard.move(-1, 0)
            state.render_needed = True
        elif self._connect_state in (self._ST_NETWORKS, self._ST_SCANNING):
            self._cancel_connect()
        else:
            super().on_left()
    
    def on_right(self):
        if self._connect_state == self._ST_PASSWORD:
            self._keyboard.move(1, 0)
            state.render_needed = True
        elif self._connect_state == self._ST_NETWORKS:
            self._select_network()
        else:
            super().on_right()
    
    def on_press(self):
        if self._connect_state == self._ST_NETWORKS:
            self._select_network()
        elif self._connect_state == self._ST_PASSWORD:
            result = self._keyboard.select()
            if result == 'DONE':
                self._do_connect()
            state.render_needed = True
        elif self._connect_state is not None:
            pass  # Ignore press during scanning/connecting
        else:
            super().on_press()
    
    def on_key1(self):
        if self._connect_state is not None:
            pass  # K1 unused during connect flow
        else:
            super().on_key1()
    
    def on_key2(self):
        if self._connect_state == self._ST_PASSWORD:
            self._keyboard.toggle_shift()
            state.render_needed = True
        elif self._connect_state is not None:
            pass  # Block mode change during connect flow
        else:
            super().on_key2()
    
    def on_key3(self):
        if self._connect_state is not None:
            self._cancel_connect()
        elif state.is_payload_running():
            payload_runner.cancel()
        else:
            self._refresh_interface_info()
            state.render_needed = True
    
    # -----------------------------------------------------------------
    # Rendering
    # -----------------------------------------------------------------
    
    def render(self) -> Image.Image:
        if self._connect_state is not None:
            return self._render_connect()
        
        # Normal WiFi attack menu
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
    
    def _render_connect(self) -> Image.Image:
        """Render WiFi Connect sub-mode screens."""
        canvas = self._create_canvas()
        
        if self._connect_state == self._ST_SCANNING:
            canvas.text(2, 2, "WIFI CONNECT", colour='title', font='title')
            canvas.text(20, 55, "Scanning...", colour='info', font='medium')
            canvas.footer("K3:Cancel")
        
        elif self._connect_state == self._ST_NETWORKS:
            self._render_network_list(canvas)
        
        elif self._connect_state == self._ST_PASSWORD:
            self._render_password(canvas)
        
        elif self._connect_state == self._ST_CONNECTING:
            canvas.text(2, 2, "WIFI CONNECT", colour='title', font='title')
            ssid = self._selected_ssid[:18]
            canvas.text(2, 25, ssid, colour='highlight', font='small')
            canvas.text(20, 55, "Connecting...", colour='info', font='medium')
            canvas.footer("Please wait")
        
        return canvas.get_image()
    
    def _render_network_list(self, canvas: Canvas):
        """Render the scanned network list."""
        canvas.text(2, 2, "SELECT NETWORK", colour='title', font='title')
        y = 18
        
        visible = self._networks[self._net_scroll:self._net_scroll + self._NET_VISIBLE]
        
        for i, net in enumerate(visible):
            actual_idx = self._net_scroll + i
            is_sel = (actual_idx == self._net_selected)
            
            if is_sel:
                canvas.rect(0, y - 1, 124, y + 11, fill='bg_selected')
            
            # Signal bar icon
            sig = net['signal']
            if sig >= 70:
                sig_icon = "▂▄▆█"
            elif sig >= 50:
                sig_icon = "▂▄▆ "
            elif sig >= 30:
                sig_icon = "▂▄  "
            else:
                sig_icon = "▂   "
            
            sig_colour = 'ok' if sig >= 50 else 'warning' if sig >= 30 else 'error'
            
            ssid = net['ssid'][:14]
            text_colour = 'text' if is_sel else 'text_dim'
            canvas.text(2, y, ssid, colour=text_colour, font='tiny')
            canvas.text(95, y, f"{sig:2}%", colour=sig_colour, font='tiny')
            
            # Lock icon for encrypted
            if net['security'] != "Open":
                canvas.text(115, y, "*", colour='warning', font='tiny')
            
            y += 12
        
        # Scroll indicator
        total = len(self._networks)
        if total > self._NET_VISIBLE:
            canvas.text(90, 2, f"{self._net_selected + 1}/{total}",
                        colour='text_dim', font='tiny')
        
        canvas.footer("●:Select  K3:Cancel")
    
    def _render_password(self, canvas: Canvas):
        """Render the password entry screen."""
        ssid = self._selected_ssid[:16]
        canvas.text(2, 2, ssid, colour='title', font='title')
        
        # Password input line
        self._keyboard.render_input_line(canvas, y=18)
        
        # Shift indicator
        if self._keyboard.shifted:
            canvas.text(110, 2, "ABC", colour='warning', font='tiny')
        
        # Keyboard grid
        self._keyboard.render(canvas, y_start=32)
        
        canvas.footer("K2:Shift  K3:Cancel")
