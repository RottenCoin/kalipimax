#!/usr/bin/env python3
"""
KaliPiMax Configuration
All hardware pins, paths, colours, and settings in one place.
"""

from pathlib import Path

# =============================================================================
# HARDWARE - GPIO Pin Definitions (BCM numbering)
# =============================================================================
# Waveshare 1.44" LCD HAT buttons
GPIO_PINS = {
    "KEY1": 22,     # Top button (was 21, conflicts with I2C)
    "KEY2": 20,     # Middle button
    "KEY3": 16,     # Bottom button
    "UP": 6,        # Joystick up
    "DOWN": 19,     # Joystick down
    "LEFT": 5,      # Joystick left
    "RIGHT": 26,    # Joystick right
    "PRESS": 13,    # Joystick centre press
}

# LCD SPI pins (directly on HAT, directly on HAT directly through HAT connector)
LCD_RST_PIN = 27
LCD_DC_PIN = 25
LCD_CS_PIN = 8
LCD_BL_PIN = 24

# Display dimensions
DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 128

# Display offsets (vary by HAT revision)
# V4 typically requires y_offset=3 to prevent bottom-line corruption
LCD_X_OFFSET = 2
LCD_Y_OFFSET = 3

import os

# =============================================================================
# PATHS
# =============================================================================
BASE_DIR = Path(os.getenv("KPM_HOME", Path(__file__).resolve().parent))
LOOT_DIR = BASE_DIR / "loot"
PAYLOADS_DIR = BASE_DIR / "payloads"
CONFIG_FILE = BASE_DIR / "config.yaml"

# Loot subdirectories
LOOT_SUBDIRS = ["nmap", "responder", "mitm", "deauth", "wifi", "shells", "captures"]

# =============================================================================
# FONTS
# =============================================================================
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono"
FONT_SIZES = {
    "title": 14,
    "large": 12,
    "medium": 11,
    "small": 9,
    "tiny": 8,
}

# =============================================================================
# COLOURS (RGB tuples)
# =============================================================================
COLOURS = {
    # Background
    "bg": (0, 0, 0),
    "bg_selected": (40, 60, 100),
    "bg_header": (20, 20, 40),
    "bg_warning": (40, 40, 0),
    
    # Text
    "title": (0, 255, 255),      # Cyan
    "text": (255, 255, 255),     # White
    "text_dim": (128, 128, 128), # Grey
    "highlight": (255, 255, 0),  # Yellow
    
    # Status
    "ok": (0, 255, 0),           # Green
    "warning": (255, 165, 0),    # Orange
    "error": (255, 0, 0),        # Red
    "info": (100, 150, 255),     # Light blue
    
    # UI elements
    "bar_cpu": (0, 200, 100),
    "bar_mem": (0, 150, 255),
    "bar_disk": (200, 100, 255),
    "scrollbar_bg": (30, 30, 30),
    "scrollbar_thumb": (100, 100, 100),
}

# =============================================================================
# TIMING
# =============================================================================
BACKLIGHT_TIMEOUT = 60          # Seconds before backlight off
BUTTON_DEBOUNCE = 0.02          # Button debounce delay
BUTTON_HOLD_TIMEOUT = 1.0       # Seconds to detect hold
RENDER_INTERVAL = 0.5           # Seconds between renders (when idle)
RENDER_INTERVAL_ACTIVE = 0.1    # Seconds between renders (when payload running)
DATA_REFRESH_INTERVAL = 2.0     # Seconds between data refreshes
PAYLOAD_TIMEOUT = 300           # Default payload timeout (5 min)
CONFIRM_TIMEOUT = 3.0           # Seconds to confirm destructive action

# =============================================================================
# NETWORK DEFAULTS
# =============================================================================
WIFI_INTERFACE = "wlan0"        # Built-in WiFi
WIFI_MONITOR_INTERFACE = "wlan1"  # External adapter for monitor mode
ETH_INTERFACE = "eth0"          # Ethernet
USB_INTERFACE = "usb0"          # USB gadget

# =============================================================================
# PAYLOAD SETTINGS
# =============================================================================
NMAP_TIMING = "-T4"             # Nmap timing template
DEAUTH_COUNT = 10               # Deauth packets to send
DEAUTH_TIMEOUT = 30             # Deauth attack duration
RESPONDER_TIMEOUT = 300         # Responder run time
MITM_TIMEOUT = 60               # MITM attack duration
CAPTURE_TIMEOUT = 30            # Packet capture duration

# =============================================================================
# UI SETTINGS
# =============================================================================
MENU_VISIBLE_ITEMS = 7          # Number of menu items visible
ALERT_MAX_COUNT = 50            # Maximum alerts to keep
PROCESS_LIST_COUNT = 20         # Processes to show
SCROLL_INDICATOR_WIDTH = 3      # Scrollbar width in pixels
