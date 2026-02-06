# KaliPiMax

**Raspberry Pi Offensive Security Toolkit with 1.44" LCD Control**


![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi-red?style=flat-square&logo=raspberry-pi)
![Python](https://img.shields.io/badge/python-3.9+-blue?style=flat-square&logo=python)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen?style=flat-square)

⚠️ **For educational and authorised testing purposes ONLY. Unauthorised access is illegal.**

---

## Features

### 13 Operational Modes
| Mode | Description |
|------|-------------|
| **SYSTEM** | CPU, RAM, temperature, IP + reboot/shutdown |
| **NETWORK** | Interface statistics, gateway, DNS |
| **NMAP** | Network reconnaissance (7 scan types) |
| **WIFI** | Monitor mode, deauth, handshake capture |
| **RESPONDER** | LLMNR/NBT-NS credential poisoning |
| **MITM** | ARP spoof, DNS spoof, packet capture |
| **SHELLS** | Reverse shell listeners (NC, Socat, MSF) |
| **USB** | HID attacks, USB gadget modes |
| **PROCESSES** | View/kill running processes |
| **LOOT** | Browse captured data files |
| **PROFILES** | Mission profile quick-setup |
| **TOOLS** | Quick tool launcher with status |
| **ALERTS** | System event log |

### Architecture
- **Thread-safe state management** with proper synchronisation
- **Modular design** - easy to add new modes
- **Centralised configuration** - one file for all settings
- **Proper logging** to file and console
- **Desktop simulator** for development without hardware
- **Comprehensive test suite** with pytest

---

## Hardware Requirements

| Component | Specification |
|-----------|--------------|
| **Raspberry Pi** | Zero 2 WH (recommended) / Pi 3 / Pi 4 |
| **Display** | Waveshare 1.44" LCD HAT (ST7735S, 128x128) |
| **MicroSD** | 32GB+ recommended |
| **Power** | 5V 2.5A minimum |

### Optional
- USB WiFi adapter with monitor mode (RTL8812AU, AR9271)
- Ethernet adapter for Pi Zero

---

## Quick Start

### On Raspberry Pi
```bash
# Clone/copy files
git clone https://github.com/kalipimax/kalipimax.git
cd kalipimax

# Install
sudo bash install.sh

# Start
sudo kalipi-config to enable SPI
sudo python3 main.py
```

### Desktop Simulator (for development)
```bash
# Install pygame
pip install pygame

# Run simulator
python3 simulator.py
```

---

## Controls

| Button | GPIO | Function |
|--------|------|----------|
| **KEY1** | 22 | Toggle backlight on/off |
| **KEY2** | 20 | Next mode |
| **KEY3** | 16 | Context action / **Cancel payload** |
| **UP** | 6 | Navigate up |
| **DOWN** | 19 | Navigate down |
| **LEFT** | 5 | Previous mode |
| **RIGHT** | 26 | Next mode |
| **PRESS** | 13 | Execute selected action |

### Simulator Controls
| Key | Function |
|-----|----------|
| 1, 2, 3 | KEY1, KEY2, KEY3 |
| Arrow keys | Joystick |
| Enter/Space | PRESS |
| Q/Esc | Quit |

---

## Project Structure

```
kalipimax_v2/
├── main.py              # Entry point
├── config.py            # All configuration
├── simulator.py         # Desktop simulator
├── pyproject.toml       # Modern Python packaging
├── requirements.txt     # Dependencies
├── install.sh           # Installation script
├── README.md
├── LICENCE
├── .gitignore
│
├── core/                # Core functionality
│   ├── __init__.py
│   ├── state.py         # Thread-safe state management
│   ├── hardware.py      # LCD and GPIO handling
│   ├── payload.py       # Command execution
│   └── logger.py        # Logging system
│
├── ui/                  # User interface
│   ├── __init__.py
│   ├── renderer.py      # Canvas, fonts, drawing
│   └── base_mode.py     # Base mode classes
│
├── modes/               # Operational modes (13 total)
│   ├── __init__.py
│   ├── system_mode.py
│   ├── network_mode.py
│   ├── nmap_mode.py
│   ├── wifi_mode.py
│   ├── responder_mode.py
│   ├── mitm_mode.py
│   ├── shells_mode.py
│   ├── usb_mode.py
│   ├── processes_mode.py
│   ├── loot_mode.py
│   ├── profiles_mode.py
│   ├── tools_mode.py
│   └── alerts_mode.py
│
├── actions/             # Future extensions
│   └── __init__.py
│
└── tests/               # Test suite
    ├── __init__.py
    ├── conftest.py
    ├── test_state.py
    ├── test_renderer.py
    └── test_modes.py
```

---

## Configuration

Edit `config.py` to customise:

```python
# GPIO pins
GPIO_PINS = {
    "KEY1": 22,
    "KEY2": 20,
    ...
}

# Timing
BACKLIGHT_TIMEOUT = 60      # Seconds before sleep
PAYLOAD_TIMEOUT = 300       # Default 5 minutes

# Network interfaces
WIFI_MONITOR_INTERFACE = "wlan1"
ETH_INTERFACE = "eth0"

# Paths
BASE_DIR = Path("/home/kali/kalipimax")
LOOT_DIR = BASE_DIR / "loot"
```

---

## Development

### Running Tests
```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=. --cov-report=html
```

### Code Quality
```bash
# Format code
black .
isort .

# Type checking
mypy .

# Linting
flake8 .
```

### Adding a New Mode

1. Create `modes/my_mode.py`:
```python
from ui.base_mode import MenuMode
from core.state import state, AlertLevel

class MyMode(MenuMode):
    def __init__(self):
        super().__init__("MYMODE", "🆕")
        self._menu_items = [
            {'icon': '●', 'text': 'Action 1', 'action': self._action1},
        ]
    
    def _action1(self):
        state.add_alert("Action executed!", AlertLevel.OK)
```

2. Register in `modes/__init__.py`:
```python
from modes.my_mode import MyMode

def get_all_modes():
    return [
        ...
        MyMode(),
    ]
```

---

## Service Management

```bash
# Enable at boot
sudo systemctl enable kalipimax

# Start/stop/restart
sudo systemctl start kalipimax
sudo systemctl stop kalipimax
sudo systemctl restart kalipimax

# View logs
sudo journalctl -u kalipimax -f
```

---

## Troubleshooting

### Display Not Working
```bash
# Check SPI enabled
ls /dev/spidev*

# Enable SPI
sudo raspi-config  # Interface Options → SPI → Enable
sudo reboot
```

### Button Not Responding
```bash
# Test GPIO
python3 -c "
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(22, GPIO.IN, pull_up_down=GPIO.PUD_UP)
print('Press KEY1...')
import time
for _ in range(50):
    if GPIO.input(22) == 0:
        print('KEY1 pressed!')
        break
    time.sleep(0.1)
GPIO.cleanup()
"
```

### WiFi Monitor Mode Issues
```bash
# Check interface exists
iw dev

# Check driver supports monitor mode
iw list | grep -A 10 "Supported interface modes"
```

---

## Security Notice

⚠️ **This tool is for authorised testing only.**

- Only use on networks you own or have explicit written permission to test
- Unauthorised access to computer systems is illegal in most jurisdictions
- The authors accept no responsibility for misuse
- Always follow responsible disclosure practices

---

## Changelog

### v2.0.0
- Complete architectural rewrite
- Fixed all critical bugs from v1
- Added 4 new modes (USB, Loot, Processes, Tools)
- Thread-safe state management
- Desktop simulator for development
- Comprehensive test suite
- Modern Python packaging (pyproject.toml)
- Proper logging system
- Centralised configuration

---

## Credits

- Inspired by [Raspyjack](https://github.com/7h30th3r0n3/Raspyjack)
- Waveshare LCD documentation
- Kali Linux team

---

## Licence

MIT Licence - See [LICENCE](LICENCE) file
