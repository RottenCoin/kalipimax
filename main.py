#!/usr/bin/env python3
"""
KaliPiMax - Raspberry Pi Offensive Security Toolkit
Main entry point with hardware initialisation and event loop.

Hardware: Raspberry Pi Zero 2 WH + Waveshare 1.44" LCD HAT

Controls:
    KEY1: Toggle backlight
    KEY2: Next mode
    KEY3: Context action (mode-specific) / Cancel payload
    UP/DOWN: Navigate menu
    LEFT/RIGHT: Change mode
    PRESS: Execute selected action
"""

import sys
import signal
import time
import threading
from pathlib import Path

# Ensure we can import our modules
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    BASE_DIR, LOOT_DIR, LOOT_SUBDIRS,
    RENDER_INTERVAL, RENDER_INTERVAL_ACTIVE
)
from core.state import state, AlertLevel
from core.hardware import hardware
from core.payload import payload_runner
from core.logger import log
from modes import get_all_modes


def create_directories():
    """Create required directories."""
    for subdir in LOOT_SUBDIRS:
        path = LOOT_DIR / subdir
        path.mkdir(parents=True, exist_ok=True)
    log.info(f"Loot directory: {LOOT_DIR}")


def handle_button(button_name: str):
    """
    Global button handler.
    Dispatches button events to appropriate handlers.
    """
    if not state.running:
        return
    
    state.render_needed = True
    
    # Wake display if off
    if hardware.wake_display(state):
        return  # Don't process button if just waking
    
    state.reset_activity()
    
    # Get current mode
    mode = state.get_current_mode()
    if not mode:
        return
    
    # Global KEY3 handling: cancel payload if running
    if button_name == 'KEY3' and state.is_payload_running():
        payload_runner.cancel()
        return
    
    # Dispatch to mode handlers
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
            log.error(f"Button handler error ({button_name}): {e}")
            state.add_alert(f"Error: {str(e)[:30]}", AlertLevel.ERROR)


def render_loop():
    """
    Main render loop.
    Renders current mode to display at regular intervals.
    """
    log.info("Render loop started")
    
    while state.running:
        try:
            if state.backlight_on and state.render_needed:
                mode = state.get_current_mode()
                if mode:
                    img = mode.render()
                    if img:
                        hardware.lcd.show_image(img)
                        state.render_needed = False
            
            # Faster updates when payload running
            interval = RENDER_INTERVAL_ACTIVE if state.is_payload_running() else RENDER_INTERVAL
            time.sleep(interval)
            
            # Force re-render periodically for live data
            state.render_needed = True
            
        except Exception as e:
            log.error(f"Render error: {e}")
            time.sleep(1)


def cleanup(signum=None, frame=None):
    """Clean shutdown handler."""
    print("\n" + "=" * 50)
    print("Shutting down KaliPiMax...")
    print("=" * 50)
    
    state.running = False
    time.sleep(0.3)
    
    # Cancel any running payloads
    if state.is_payload_running():
        payload_runner.cancel()
    
    # Clean up hardware
    hardware.cleanup()
    
    print("Shutdown complete")
    sys.exit(0)


def main():
    """Main entry point."""
    print("=" * 60)
    print("  KaliPiMax - Raspberry Pi Offensive Security Toolkit")
    print("=" * 60)
    print()
    
    # Create directories
    create_directories()
    
    # Initialise hardware
    if not hardware.init():
        print("ERROR: Hardware initialisation failed!")
        print("Check SPI is enabled: sudo raspi-config")
        sys.exit(1)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    # Load modes
    modes = get_all_modes()
    state.modes = modes
    
    print(f"\nLoaded {len(modes)} modes:")
    for i, mode in enumerate(modes):
        print(f"  [{i}] {mode.icon} {mode.name}")
    
    # Enter first mode
    if modes:
        modes[0].on_enter()
    
    # Set up button handler
    hardware.buttons.set_global_callback(handle_button)
    
    # Start hardware services
    hardware.start(state)
    
    # Start render thread
    render_thread = threading.Thread(target=render_loop, daemon=True)
    render_thread.start()
    
    print()
    print("=" * 60)
    print("  Controls:")
    print("    KEY1: Toggle backlight")
    print("    KEY2: Next mode")
    print("    KEY3: Context action / Cancel payload")
    print("    ↑↓: Navigate menu")
    print("    ←→: Change mode")
    print("    ●: Execute selected action")
    print("=" * 60)
    print()
    
    # Initial alert
    state.add_alert("KaliPiMax ready", AlertLevel.OK)
    
    # Main loop (just keeps the process alive)
    try:
        while state.running:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()


if __name__ == "__main__":
    main()
