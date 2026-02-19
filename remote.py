#!/usr/bin/env python3
"""
KaliPiMax SSH Remote Display
Terminal-based mirror of the 128x128 LCD for remote operation via SSH.

Renders the exact same display as the physical screen using ANSI
true-colour and Unicode half-block characters.

Usage:
    ssh kali@<pi-ip> 'cd ~/kalipimax && python3 remote.py'

Controls:
    Arrow keys  = Joystick (↑↓←→)
    Enter       = Joystick press (●)
    1           = KEY1
    2           = KEY2
    3           = KEY3
    Ctrl-C      = Quit
"""

import sys
import os
import time
import select
import tty
import termios
import signal
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PIL import Image
from config import DISPLAY_WIDTH, DISPLAY_HEIGHT, LOOT_DIR, LOOT_SUBDIRS
from core.state import state, AlertLevel
from core.payload import payload_runner


# =====================================================================
# Terminal display
# =====================================================================

# Unicode half-block: top pixel = foreground, bottom pixel = background
_HALF_BLOCK = '\u2580'  # ▀
_RESET = '\033[0m'


def image_to_ansi(img: Image.Image) -> str:
    """
    Convert 128x128 PIL Image to ANSI true-colour string.
    Uses half-block characters: each cell = 2 vertical pixels.
    Output: 128 columns × 64 rows.
    """
    if img.mode != 'RGB':
        img = img.convert('RGB')

    pixels = img.load()
    w, h = img.size
    lines = []

    # Move cursor home
    lines.append('\033[H')

    for row in range(0, h, 2):
        parts = []
        for col in range(w):
            r1, g1, b1 = pixels[col, row]          # top pixel
            r2, g2, b2 = pixels[col, row + 1] if row + 1 < h else (0, 0, 0)  # bottom pixel
            # fg = top pixel colour, bg = bottom pixel colour
            parts.append(
                f'\033[38;2;{r1};{g1};{b1}m'
                f'\033[48;2;{r2};{g2};{b2}m'
                f'{_HALF_BLOCK}'
            )
        lines.append(''.join(parts) + _RESET)

    return '\n'.join(lines)


# =====================================================================
# Keyboard input
# =====================================================================

def read_key(fd: int, timeout: float = 0.05) -> str:
    """
    Read a keypress from terminal. Returns button name or ''.

    Handles:
        Arrow keys (ESC [ A/B/C/D)
        Enter
        1, 2, 3
        Ctrl-C raises KeyboardInterrupt
    """
    if not select.select([fd], [], [], timeout)[0]:
        return ''

    ch = os.read(fd, 1)

    if ch == b'\x03':  # Ctrl-C
        raise KeyboardInterrupt

    if ch == b'\x1b':  # Escape sequence
        if not select.select([fd], [], [], 0.05)[0]:
            return ''  # Bare ESC — ignore
        ch2 = os.read(fd, 1)
        if ch2 == b'[':
            if not select.select([fd], [], [], 0.05)[0]:
                return ''
            ch3 = os.read(fd, 1)
            arrow_map = {
                b'A': 'UP',
                b'B': 'DOWN',
                b'C': 'RIGHT',
                b'D': 'LEFT',
            }
            return arrow_map.get(ch3, '')
        return ''

    key_map = {
        b'\r': 'PRESS',
        b'\n': 'PRESS',
        b'1': 'KEY1',
        b'2': 'KEY2',
        b'3': 'KEY3',
    }
    return key_map.get(ch, '')


# =====================================================================
# Button handler (same logic as main.py)
# =====================================================================

def handle_button(button_name: str):
    """Dispatch button event to current mode."""
    if not state.running or not button_name:
        return

    state.render_needed = True
    state.reset_activity()

    mode = state.get_current_mode()
    if not mode:
        return

    # Global KEY3: cancel payload if running
    if button_name == 'KEY3' and state.is_payload_running():
        payload_runner.cancel()
        return

    handlers = {
        'KEY1': mode.on_key1,
        'KEY2': mode.on_key2,
        'KEY3': mode.on_key3,
        'UP': mode.on_up,
        'DOWN': mode.on_down,
        'LEFT': mode.on_left,
        'RIGHT': mode.on_right,
        'PRESS': mode.on_press,
    }

    handler = handlers.get(button_name)
    if handler:
        try:
            handler()
        except Exception as e:
            state.add_alert(f"Error: {str(e)[:30]}", AlertLevel.ERROR)


# =====================================================================
# Main
# =====================================================================

def create_directories():
    """Create required loot directories."""
    for subdir in LOOT_SUBDIRS:
        path = LOOT_DIR / subdir
        path.mkdir(parents=True, exist_ok=True)


def kill_existing():
    """Kill any running KaliPiMax processes (main.py, simulator.py, other remote.py)."""
    import subprocess
    my_pid = os.getpid()
    targets = ['main.py', 'simulator.py', 'remote.py']

    for target in targets:
        try:
            result = subprocess.run(
                f"pgrep -f 'python.*{target}'",
                shell=True, capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.strip().splitlines():
                pid = int(line.strip())
                if pid != my_pid:
                    os.kill(pid, signal.SIGTERM)
                    print(f"  Killed {target} (PID {pid})")
        except Exception:
            pass

    # Brief pause for processes to exit
    time.sleep(0.5)


def main():
    # Kill any existing KaliPiMax processes
    print("Stopping existing KaliPiMax processes...")
    kill_existing()

    # Ensure directories exist
    create_directories()

    # Import modes (triggers hardware detection — will fall back to sim)
    from modes import get_all_modes
    modes = get_all_modes()
    state.modes = modes

    if modes:
        modes[0].on_enter()
    state.add_alert("Remote connected", AlertLevel.OK)

    # Save terminal state and switch to raw mode
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    # Hide cursor, clear screen
    sys.stdout.write('\033[?25l')  # hide cursor
    sys.stdout.write('\033[2J')    # clear screen
    sys.stdout.flush()

    # Print controls bar (will be below the display)
    # 64 rows of display + 2 for status
    status_row = 66

    def show_status(text: str):
        sys.stdout.write(f'\033[{status_row};1H\033[K')
        sys.stdout.write(f'\033[38;2;100;150;255m{text}\033[0m')
        sys.stdout.flush()

    show_status(
        '↑↓←→:Navigate  Enter:Press  1:K1  2:K2  3:K3  Ctrl-C:Quit'
    )

    try:
        tty.setraw(fd)

        last_render = 0
        render_interval = 0.1  # 10 FPS

        while state.running:
            # Read input
            button = read_key(fd)
            if button:
                handle_button(button)

            # Render
            now = time.time()
            if now - last_render >= render_interval:
                mode = state.get_current_mode()
                if mode:
                    try:
                        img = mode.render()
                        if img:
                            frame = image_to_ansi(img)
                            sys.stdout.write(frame)
                            sys.stdout.flush()
                    except Exception:
                        pass
                last_render = now

            # Small sleep to avoid busy-waiting
            time.sleep(0.02)

    except KeyboardInterrupt:
        pass
    finally:
        # Restore terminal
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        sys.stdout.write('\033[?25h')  # show cursor
        sys.stdout.write(f'\033[{status_row + 2};1H')  # move below display
        sys.stdout.write('\033[0m')    # reset colours
        sys.stdout.flush()
        state.running = False
        print("\nRemote display closed.")


if __name__ == '__main__':
    main()
