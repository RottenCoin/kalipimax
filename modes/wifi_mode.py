#!/usr/bin/env python3
"""
KaliPiMax WiFi Mode
Wireless attacks, monitoring, reconnaissance, and WiFi connectivity.

WiFi Connect flow:
    Scan → Select network → Enter password (or use stored) → Connect →
    "Use tools on this network?" Y/N →
    Y: connect wlan1 to same network for attacks
    N: wlan0 only, non-aggressive use
"""

import subprocess
import re
import threading
from PIL import Image

from ui.base_mode import MenuMode
from ui.renderer import Canvas
from ui.keyboard import OnScreenKeyboard
from ui.prompt import YNPrompt
from core.state import state, AlertLevel
from core.payload import payload_runner, get_loot_path
from core import wifi_profiles
from core.wifi_tools import prepare_monitor, restore_after_monitor
from config import (
    WIFI_INTERFACE, WIFI_MONITOR_INTERFACE,
    DEAUTH_COUNT, DEAUTH_TIMEOUT, DISPLAY_HEIGHT
)


# =====================================================================
# Helpers
# =====================================================================

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
            mac_result = subprocess.run(
                f"cat /sys/class/net/{interface}/address",
                shell=True, capture_output=True, text=True, timeout=2
            )
            if mac_result.returncode == 0:
                info['mac'] = mac_result.stdout.strip()[:17]
    except Exception:
        pass
    return info


def scan_wifi_networks() -> list:
    """Scan for WiFi networks using nmcli on wlan0."""
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
                'known': wifi_profiles.is_known(ssid),
            })

        networks.sort(key=lambda n: n['signal'], reverse=True)
        return networks
    except Exception:
        return []


def wifi_connect(ssid: str, password: str, interface: str = WIFI_INTERFACE) -> tuple:
    """
    Connect to a WiFi network. Returns (success: bool, error: str).
    """
    try:
        safe_ssid = ssid.replace("'", "'\\''")
        safe_pw = password.replace("'", "'\\''")
        cmd = (
            f"nmcli device wifi connect '{safe_ssid}' "
            f"password '{safe_pw}' ifname {interface}"
        )
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return True, ""
        err = result.stderr.strip()[:40] or result.stdout.strip()[:40] or "Failed"
        return False, err
    except subprocess.TimeoutExpired:
        return False, "Connection timeout"
    except Exception as e:
        return False, str(e)[:30]


def ensure_wlan1_mode(target_mode: str) -> bool:
    """
    Ensure WIFI_MONITOR_INTERFACE is in the required mode.
    target_mode: 'managed' or 'monitor'.
    Returns True on success.
    """
    iface = WIFI_MONITOR_INTERFACE
    mon_iface = f"{WIFI_MONITOR_INTERFACE}mon"
    current = get_interface_info(mon_iface)

    if target_mode == 'monitor':
        # Check if already in monitor
        if current['exists'] and current['mode'] == 'monitor':
            return True
        # Switch to monitor
        try:
            subprocess.run(
                f"sudo airmon-ng check kill && sudo airmon-ng start {iface}",
                shell=True, capture_output=True, timeout=15
            )
            return True
        except Exception:
            return False

    elif target_mode == 'managed':
        # If monitor interface exists, stop it
        if current['exists'] and current['mode'] == 'monitor':
            try:
                subprocess.run(
                    f"sudo airmon-ng stop {mon_iface}",
                    shell=True, capture_output=True, timeout=10
                )
            except Exception:
                return False

        # Reconnect to target network if tools mode is active
        if state.tools_on_target:
            ok, _ = wifi_connect(
                state.target_ssid, state.target_password,
                interface=iface
            )
            return ok
        return True

    return False


# =====================================================================
# WiFiMode
# =====================================================================

class WiFiMode(MenuMode):
    """
    WiFi attack and monitoring mode.

    Includes WiFi Connect flow with credential storage and
    tools-on-target prompt.
    """

    # Connect sub-mode states
    _ST_NONE = None
    _ST_SCANNING = 'scanning'
    _ST_NETWORKS = 'networks'
    _ST_AUTO_CONNECT = 'auto_connect'
    _ST_PW_CHANGED = 'pw_changed'
    _ST_PASSWORD = 'password'
    _ST_CONNECTING = 'connecting'
    _ST_TOOLS_PROMPT = 'tools_prompt'
    _ST_TOOLS_CONNECT = 'tools_connect'

    _NET_VISIBLE = 8

    def __init__(self):
        super().__init__("WIFI", "📡")

        self._interface = WIFI_MONITOR_INTERFACE
        self._monitor_iface = f"{WIFI_MONITOR_INTERFACE}mon"

        self._menu_items = [
            {'icon': '◉', 'text': 'WiFi Connect', 'action': self._start_connect},
            {'icon': '●', 'text': 'Monitor Mode ON', 'action': self._enable_monitor},
            {'icon': '●', 'text': 'Monitor Mode OFF', 'action': self._disable_monitor},
            {'icon': '●', 'text': 'WiFi Scan (atk)', 'action': self._scan_networks},
            {'icon': '●', 'text': 'Deauth Attack', 'action': self._deauth_attack},
            {'icon': '●', 'text': 'Capture Handshake', 'action': self._capture_handshake},
            {'icon': '●', 'text': 'MAC Randomise', 'action': self._randomise_mac},
            {'icon': '●', 'text': 'Interface Info', 'action': self._show_info},
        ]

        self._iface_info = {}

        # Connect flow state
        self._cstate = self._ST_NONE
        self._networks = []
        self._net_selected = 0
        self._net_scroll = 0
        self._selected_ssid = ""
        self._selected_pw = ""
        self._keyboard = None
        self._prompt = None

    def on_enter(self):
        super().on_enter()
        self._refresh_interface_info()

    def _refresh_interface_info(self):
        """Refresh interface information."""
        if get_interface_info(self._monitor_iface)['exists']:
            self._iface_info = get_interface_info(self._monitor_iface)
            self._iface_info['name'] = self._monitor_iface
        else:
            self._iface_info = get_interface_info(self._interface)
            self._iface_info['name'] = self._interface

    # -----------------------------------------------------------------
    # Attack actions (unchanged)
    # -----------------------------------------------------------------

    def _enable_monitor(self):
        payload_runner.run(
            f"sudo airmon-ng check kill && sudo airmon-ng start {self._interface}",
            "Enable Monitor", timeout=30,
            on_complete=self._refresh_interface_info
        )

    def _disable_monitor(self):
        payload_runner.run(
            f"sudo airmon-ng stop {self._monitor_iface} && "
            f"sudo systemctl restart NetworkManager",
            "Disable Monitor", timeout=30,
            on_complete=self._refresh_interface_info
        )

    def _scan_networks(self):
        iface = prepare_monitor()
        if not iface:
            return
        outfile = get_loot_path("wifi", "scan", "csv")
        outfile_base = outfile.replace('.csv', '')
        payload_runner.run(
            f"sudo airodump-ng {iface} "
            f"--write {outfile_base} --output-format csv",
            "WiFi Scan", timeout=25,
            on_complete=restore_after_monitor
        )

    def _deauth_attack(self):
        iface = prepare_monitor()
        if not iface:
            return
        outfile = get_loot_path("deauth", "deauth", "log")
        payload_runner.run(
            f"sudo aireplay-ng --deauth {DEAUTH_COUNT} "
            f"-a FF:FF:FF:FF:FF:FF {iface} 2>&1 | tee {outfile}",
            "Deauth Attack", timeout=DEAUTH_TIMEOUT + 5,
            on_complete=restore_after_monitor
        )

    def _capture_handshake(self):
        iface = prepare_monitor()
        if not iface:
            return
        outfile = get_loot_path("wifi", "handshake", "cap")
        outfile_base = outfile.replace('.cap', '')
        payload_runner.run(
            f"sudo airodump-ng {iface} "
            f"--write {outfile_base} --output-format pcap",
            "Capture Handshake", timeout=65,
            on_complete=restore_after_monitor
        )

    def _randomise_mac(self):
        payload_runner.run(
            f"sudo ip link set {self._interface} down && "
            f"sudo macchanger -r {self._interface} && "
            f"sudo ip link set {self._interface} up",
            "MAC Randomise", timeout=10,
            on_complete=self._refresh_interface_info
        )

    def _show_info(self):
        self._refresh_interface_info()
        info = self._iface_info
        state.add_alert(
            f"{info.get('name', 'N/A')}: {info.get('mode', 'N/A')}",
            AlertLevel.INFO
        )

    # -----------------------------------------------------------------
    # WiFi Connect flow
    # -----------------------------------------------------------------

    def _start_connect(self):
        """Begin WiFi Connect — scan for networks."""
        self._cstate = self._ST_SCANNING
        self._networks = []
        state.render_needed = True

        def _do_scan():
            nets = scan_wifi_networks()
            self._networks = nets
            if nets:
                self._cstate = self._ST_NETWORKS
                self._net_selected = 0
                self._net_scroll = 0
            else:
                state.add_alert("No networks found", AlertLevel.WARNING)
                self._cstate = self._ST_NONE
            state.render_needed = True

        threading.Thread(target=_do_scan, daemon=True).start()

    def _select_network(self):
        """User picked a network from the list."""
        if not self._networks or self._net_selected >= len(self._networks):
            return
        net = self._networks[self._net_selected]
        self._selected_ssid = net['ssid']

        if net['known']:
            # Try stored password
            self._selected_pw = wifi_profiles.get_password(self._selected_ssid) or ""
            self._cstate = self._ST_AUTO_CONNECT
            state.render_needed = True
            threading.Thread(target=self._try_auto_connect, daemon=True).start()
        else:
            # New network — open keyboard
            self._open_keyboard()

    def _try_auto_connect(self):
        """Attempt connection with stored password."""
        ok, err = wifi_connect(self._selected_ssid, self._selected_pw)
        if ok:
            state.add_alert(f"Connected: {self._selected_ssid[:18]}", AlertLevel.OK)
            self._show_tools_prompt()
        else:
            # Password may have changed
            self._prompt = YNPrompt("Password changed.\nType new password?")
            self._cstate = self._ST_PW_CHANGED
        state.render_needed = True

    def _open_keyboard(self):
        """Open on-screen keyboard for password entry."""
        self._keyboard = OnScreenKeyboard(max_length=63)
        self._cstate = self._ST_PASSWORD
        state.render_needed = True

    def _submit_password(self):
        """User pressed DONE on keyboard — try connecting."""
        self._selected_pw = self._keyboard.text
        self._cstate = self._ST_CONNECTING
        state.render_needed = True

        def _try_connect():
            ok, err = wifi_connect(self._selected_ssid, self._selected_pw)
            if ok:
                wifi_profiles.store_password(self._selected_ssid, self._selected_pw)
                state.add_alert(f"Connected: {self._selected_ssid[:18]}", AlertLevel.OK)
                self._show_tools_prompt()
            else:
                state.add_alert(f"Failed: {err}", AlertLevel.ERROR)
                # Back to keyboard to retry
                self._open_keyboard()
            state.render_needed = True

        threading.Thread(target=_try_connect, daemon=True).start()

    def _show_tools_prompt(self):
        """Show Y/N: use tools on this network?"""
        self._prompt = YNPrompt("Use tools on\nthis network?")
        self._cstate = self._ST_TOOLS_PROMPT
        state.render_needed = True

    def _handle_tools_answer(self):
        """Process the tools prompt answer."""
        if self._prompt.confirm():
            # Y — connect wlan1 to same network
            self._cstate = self._ST_TOOLS_CONNECT
            state.render_needed = True
            threading.Thread(target=self._connect_wlan1, daemon=True).start()
        else:
            # N — wlan0 only
            state.clear_tools_on_target()
            state.add_alert("WiFi ready (no tools)", AlertLevel.OK)
            self._cstate = self._ST_NONE
            state.render_needed = True

    def _connect_wlan1(self):
        """Connect wlan1 to target network for tool use."""
        ssid = self._selected_ssid
        pw = self._selected_pw

        # Make sure wlan1 is in managed mode
        ensure_wlan1_mode('managed')

        ok, err = wifi_connect(ssid, pw, interface=WIFI_MONITOR_INTERFACE)
        if ok:
            state.set_tools_on_target(ssid, pw)
            state.add_alert(f"Tools ready: {ssid[:16]}", AlertLevel.OK)
        else:
            state.clear_tools_on_target()
            state.add_alert(f"wlan1 failed: {err}", AlertLevel.ERROR)

        self._cstate = self._ST_NONE
        state.render_needed = True

    def _cancel_connect(self):
        """Cancel connect flow and return to menu."""
        self._cstate = self._ST_NONE
        self._keyboard = None
        self._prompt = None
        state.render_needed = True

    # -----------------------------------------------------------------
    # Button handlers
    # -----------------------------------------------------------------

    def on_up(self):
        if self._cstate == self._ST_NETWORKS:
            if self._net_selected > 0:
                self._net_selected -= 1
                if self._net_selected < self._net_scroll:
                    self._net_scroll = self._net_selected
                state.render_needed = True
        elif self._cstate == self._ST_PASSWORD:
            self._keyboard.move(0, -1)
            state.render_needed = True
        elif self._cstate is None:
            super().on_up()

    def on_down(self):
        if self._cstate == self._ST_NETWORKS:
            if self._net_selected < len(self._networks) - 1:
                self._net_selected += 1
                if self._net_selected >= self._net_scroll + self._NET_VISIBLE:
                    self._net_scroll = self._net_selected - self._NET_VISIBLE + 1
                state.render_needed = True
        elif self._cstate == self._ST_PASSWORD:
            self._keyboard.move(0, 1)
            state.render_needed = True
        elif self._cstate is None:
            super().on_down()

    def on_left(self):
        if self._cstate == self._ST_PASSWORD:
            self._keyboard.move(-1, 0)
            state.render_needed = True
        elif self._cstate in (self._ST_TOOLS_PROMPT, self._ST_PW_CHANGED):
            self._prompt.move(-1)
            state.render_needed = True
        elif self._cstate in (self._ST_NETWORKS, self._ST_SCANNING):
            self._cancel_connect()
        elif self._cstate is None:
            super().on_left()

    def on_right(self):
        if self._cstate == self._ST_PASSWORD:
            self._keyboard.move(1, 0)
            state.render_needed = True
        elif self._cstate in (self._ST_TOOLS_PROMPT, self._ST_PW_CHANGED):
            self._prompt.move(1)
            state.render_needed = True
        elif self._cstate == self._ST_NETWORKS:
            self._select_network()
        elif self._cstate is None:
            super().on_right()

    def on_press(self):
        if self._cstate == self._ST_NETWORKS:
            self._select_network()
        elif self._cstate == self._ST_PASSWORD:
            result = self._keyboard.select()
            if result == 'DONE':
                self._submit_password()
            state.render_needed = True
        elif self._cstate == self._ST_TOOLS_PROMPT:
            self._handle_tools_answer()
        elif self._cstate == self._ST_PW_CHANGED:
            if self._prompt.confirm():
                self._open_keyboard()
            else:
                self._cstate = self._ST_NETWORKS
                state.render_needed = True
        elif self._cstate is not None:
            pass  # Ignore during scanning/connecting
        else:
            super().on_press()

    def on_key1(self):
        if self._cstate is not None:
            pass
        else:
            super().on_key1()

    def on_key2(self):
        if self._cstate == self._ST_PASSWORD:
            self._keyboard.toggle_shift()
            state.render_needed = True
        elif self._cstate is not None:
            pass
        else:
            super().on_key2()

    def on_key3(self):
        if self._cstate is not None:
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
        if self._cstate is not None:
            return self._render_connect()

        # Normal WiFi attack menu
        canvas = self._create_canvas()
        y = self._render_header(canvas, "WIFI ATTACK")

        info = self._iface_info
        iface_name = info.get('name', 'N/A')
        mode = info.get('mode', 'unknown')
        mode_colour = 'ok' if mode == 'monitor' else 'warning' if mode == 'managed' else 'error'
        canvas.text(2, y, f"{iface_name}: ", colour='text_dim', font='tiny')
        canvas.text(55, y, mode.upper(), colour=mode_colour, font='tiny')

        # Show tools-on-target indicator
        if state.tools_on_target:
            canvas.text(2, y + 9, f"TARGET: {state.target_ssid[:14]}", colour='ok', font='tiny')
            y += 10

        y += 10
        self._menu.start_y = y
        self._render_menu(canvas, start_y=y)
        self._render_footer(canvas, "K3:Refresh/Cancel")
        return canvas.get_image()

    def _render_connect(self) -> Image.Image:
        """Render WiFi Connect sub-mode screens."""
        canvas = self._create_canvas()

        if self._cstate == self._ST_SCANNING:
            canvas.text(2, 2, "WIFI CONNECT", colour='title', font='title')
            canvas.text(20, 55, "Scanning...", colour='info', font='medium')
            canvas.footer("K3:Cancel")

        elif self._cstate == self._ST_NETWORKS:
            self._render_network_list(canvas)

        elif self._cstate == self._ST_AUTO_CONNECT:
            canvas.text(2, 2, "WIFI CONNECT", colour='title', font='title')
            ssid = self._selected_ssid[:18]
            canvas.text(2, 25, ssid, colour='highlight', font='small')
            canvas.text(10, 50, "Trying stored", colour='info', font='small')
            canvas.text(10, 62, "password...", colour='info', font='small')
            canvas.footer("Please wait")

        elif self._cstate == self._ST_PW_CHANGED:
            canvas.text(2, 2, "WIFI CONNECT", colour='title', font='title')
            self._prompt.render(canvas, y_start=22)
            canvas.footer("←→:Choose  ●:Confirm")

        elif self._cstate == self._ST_PASSWORD:
            self._render_password(canvas)

        elif self._cstate == self._ST_CONNECTING:
            canvas.text(2, 2, "WIFI CONNECT", colour='title', font='title')
            ssid = self._selected_ssid[:18]
            canvas.text(2, 25, ssid, colour='highlight', font='small')
            canvas.text(20, 55, "Connecting...", colour='info', font='medium')
            canvas.footer("Please wait")

        elif self._cstate == self._ST_TOOLS_PROMPT:
            canvas.text(2, 2, "WIFI CONNECT", colour='title', font='title')
            self._prompt.render(canvas, y_start=22)
            canvas.footer("←→:Choose  ●:Confirm")

        elif self._cstate == self._ST_TOOLS_CONNECT:
            canvas.text(2, 2, "WIFI CONNECT", colour='title', font='title')
            canvas.text(10, 40, "Connecting", colour='info', font='small')
            canvas.text(10, 52, f"wlan1...", colour='info', font='small')
            canvas.footer("Please wait")

        return canvas.get_image()

    def _render_network_list(self, canvas: Canvas):
        """Render scanned network list with known-network indicators."""
        canvas.text(2, 2, "SELECT NETWORK", colour='title', font='title')
        y = 18

        visible = self._networks[self._net_scroll:self._net_scroll + self._NET_VISIBLE]

        for i, net in enumerate(visible):
            actual_idx = self._net_scroll + i
            is_sel = (actual_idx == self._net_selected)

            if is_sel:
                canvas.rect(0, y - 1, 124, y + 11, fill='bg_selected')

            # Known indicator
            if net['known']:
                canvas.text(2, y, "★", colour='ok', font='tiny')
                x_ssid = 12
            else:
                x_ssid = 2

            ssid = net['ssid'][:13 if net['known'] else 14]
            text_colour = 'text' if is_sel else 'text_dim'
            canvas.text(x_ssid, y, ssid, colour=text_colour, font='tiny')

            sig = net['signal']
            sig_colour = 'ok' if sig >= 50 else 'warning' if sig >= 30 else 'error'
            canvas.text(95, y, f"{sig:2}%", colour=sig_colour, font='tiny')

            if net['security'] != "Open":
                canvas.text(118, y, "*", colour='warning', font='tiny')

            y += 12

        total = len(self._networks)
        if total > self._NET_VISIBLE:
            canvas.text(85, 2, f"{self._net_selected + 1}/{total}",
                        colour='text_dim', font='tiny')

        canvas.footer("●:Select  K3:Cancel")

    def _render_password(self, canvas: Canvas):
        """Render password entry screen."""
        ssid = self._selected_ssid[:16]
        canvas.text(2, 2, ssid, colour='title', font='title')
        self._keyboard.render_input_line(canvas, y=18)
        if self._keyboard.shifted:
            canvas.text(110, 2, "ABC", colour='warning', font='tiny')
        self._keyboard.render(canvas, y_start=32)
        canvas.footer("K2:Shift  K3:Cancel")
