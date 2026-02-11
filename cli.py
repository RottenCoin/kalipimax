#!/usr/bin/env python3
"""
KaliPiMax Headless CLI
Run payloads without LCD or pygame — terminal only.

Usage:
    Interactive:  python cli.py
    One-shot:     python cli.py <mode> <action_number>
    List actions: python cli.py <mode>

Examples:
    python cli.py mitm 1        # ARP Spoof (GW)
    python cli.py nmap           # list nmap actions
    python cli.py wifi 3         # run wifi action #3
"""

import sys
import signal
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import LOOT_DIR, LOOT_SUBDIRS
from core.state import state, AlertLevel
from core.payload import payload_runner

from modes.system_mode import SystemMode
from modes.nmap_mode import NmapMode
from modes.wifi_mode import WiFiMode
from modes.responder_mode import ResponderMode
from modes.mitm_mode import MITMMode
from modes.shells_mode import ShellsMode
from modes.usb_mode import USBMode
from modes.profiles_mode import ProfilesMode
from modes.tools_mode import ToolsMode


# Modes that have actionable menu items, keyed by short name.
MODE_CLASSES = {
    "system":    SystemMode,
    "nmap":      NmapMode,
    "wifi":      WiFiMode,
    "responder": ResponderMode,
    "mitm":      MITMMode,
    "shells":    ShellsMode,
    "usb":       USBMode,
    "profiles":  ProfilesMode,
    "tools":     ToolsMode,
}


def create_directories():
    """Create required loot directories."""
    for subdir in LOOT_SUBDIRS:
        (LOOT_DIR / subdir).mkdir(parents=True, exist_ok=True)


def init_mode(name: str):
    """Instantiate a mode and call on_enter so dynamic menus populate."""
    cls = MODE_CLASSES[name]
    mode = cls()
    mode.on_enter()
    return mode


def get_actions(mode) -> list:
    """Return list of (index, text, callable) for a mode's menu items."""
    actions = []
    for i, item in enumerate(mode._menu_items):
        text = item.get("text", f"Action {i}")
        action = item.get("action")
        if action and callable(action):
            actions.append((i + 1, text, action))
    return actions


def print_actions(mode_name: str, actions: list):
    """Print numbered action list for a mode."""
    print(f"\n  {mode_name.upper()} actions:")
    for num, text, _ in actions:
        print(f"    {num}. {text}")
    print()


def wait_for_payload():
    """Block until the current payload finishes."""
    if not state.is_payload_running():
        return
    print("Waiting for payload to finish (Ctrl+C to cancel)...")
    try:
        while state.is_payload_running():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nCancelling payload...")
        payload_runner.cancel()
        time.sleep(1)


def run_action(mode_name: str, action_num: int):
    """Run a single action by mode name and 1-based index."""
    mode = init_mode(mode_name)
    actions = get_actions(mode)

    if not actions:
        print(f"No actions available for {mode_name}")
        return False

    match = [a for a in actions if a[0] == action_num]
    if not match:
        print(f"Invalid action number {action_num} for {mode_name}")
        print_actions(mode_name, actions)
        return False

    _, text, action = match[0]
    print(f"Running: {mode_name} > {text}")
    action()
    wait_for_payload()
    return True


def interactive():
    """Interactive menu loop."""
    print("=" * 50)
    print("  KaliPiMax Headless CLI")
    print("=" * 50)
    print()
    print("Available modes:")
    names = list(MODE_CLASSES.keys())
    for i, name in enumerate(names, 1):
        print(f"  {i}. {name}")
    print(f"  q. Quit")

    while True:
        print()
        choice = input("Mode (number/name/q): ").strip().lower()

        if choice in ("q", "quit", "exit"):
            break

        # Accept number or name
        mode_name = None
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(names):
                mode_name = names[idx]
        elif choice in MODE_CLASSES:
            mode_name = choice

        if not mode_name:
            print("Invalid mode. Try again.")
            continue

        mode = init_mode(mode_name)
        actions = get_actions(mode)

        if not actions:
            print(f"No actions available for {mode_name}")
            continue

        print_actions(mode_name, actions)
        act = input("Action number (b=back): ").strip().lower()

        if act in ("b", "back", ""):
            continue

        if not act.isdigit():
            print("Invalid input.")
            continue

        action_num = int(act)
        match = [a for a in actions if a[0] == action_num]
        if not match:
            print("Invalid action number.")
            continue

        _, text, action = match[0]
        print(f"\nRunning: {mode_name} > {text}")
        action()
        wait_for_payload()


def cleanup(signum=None, frame=None):
    """Clean shutdown."""
    state.running = False
    if state.is_payload_running():
        payload_runner.cancel()
        time.sleep(0.5)
    print("\nClosed.")
    sys.exit(0)


def usage():
    """Print usage and exit."""
    print(__doc__)
    print("Available modes:")
    for name in MODE_CLASSES:
        print(f"  {name}")
    print()
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    create_directories()

    args = sys.argv[1:]

    # No args → interactive
    if not args:
        interactive()
        return

    if args[0] in ("-h", "--help", "help"):
        usage()

    mode_name = args[0].lower()
    if mode_name not in MODE_CLASSES:
        print(f"Unknown mode: {mode_name}")
        usage()

    # Mode name only → list actions
    if len(args) == 1:
        mode = init_mode(mode_name)
        actions = get_actions(mode)
        print_actions(mode_name, actions)
        return

    # Mode + action number → one-shot
    if not args[1].isdigit():
        print(f"Action must be a number, got: {args[1]}")
        sys.exit(1)

    run_action(mode_name, int(args[1]))


if __name__ == "__main__":
    main()
