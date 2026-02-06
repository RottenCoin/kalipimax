#!/usr/bin/env python3
"""
KaliPiMax Desktop Simulator
Run and test KaliPiMax on desktop without Raspberry Pi hardware.

Uses pygame to simulate the LCD display and keyboard for buttons.

Controls:
    1 = KEY1 (backlight)
    2 = KEY2 (next mode)
    3 = KEY3 (context action)
    ↑↓←→ = Joystick
    Enter/Space = PRESS
    Q/Esc = Quit
"""

import sys
import time
import threading
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("pygame not installed. Install with: pip install pygame")
    sys.exit(1)

from PIL import Image

from config import DISPLAY_WIDTH, DISPLAY_HEIGHT
from core.state import state, AlertLevel
from modes import get_all_modes


# Simulated LCD class
class SimulatedLCD:
    """Simulated LCD that renders to pygame window."""
    
    def __init__(self, surface, scale: int = 4):
        self.surface = surface
        self.scale = scale
        self._width = DISPLAY_WIDTH
        self._height = DISPLAY_HEIGHT
        self._initialised = True
    
    def init(self) -> bool:
        return True
    
    def show_image(self, image: Image.Image):
        """Display PIL Image on pygame surface."""
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Scale up for visibility
        scaled = image.resize(
            (self._width * self.scale, self._height * self.scale),
            Image.NEAREST
        )
        
        # Convert to pygame surface
        mode = scaled.mode
        size = scaled.size
        data = scaled.tobytes()
        
        py_image = pygame.image.fromstring(data, size, mode)
        self.surface.blit(py_image, (0, 0))
        pygame.display.flip()
    
    def clear(self, colour=(0, 0, 0)):
        self.surface.fill(colour)
        pygame.display.flip()
    
    def set_backlight(self, on: bool):
        pass  # No-op in simulator
    
    def cleanup(self):
        pass


class SimulatedButtons:
    """Simulated buttons using keyboard input."""
    
    def __init__(self):
        self._callback = None
        self._running = False
    
    def init(self) -> bool:
        return True
    
    def set_callback(self, button_name: str, callback):
        pass
    
    def set_global_callback(self, callback):
        self._callback = callback
    
    def start_polling(self):
        self._running = True
    
    def stop_polling(self):
        self._running = False
    
    def handle_key(self, key):
        """Map pygame key to button name."""
        key_map = {
            pygame.K_1: 'KEY1',
            pygame.K_2: 'KEY2',
            pygame.K_3: 'KEY3',
            pygame.K_UP: 'UP',
            pygame.K_DOWN: 'DOWN',
            pygame.K_LEFT: 'LEFT',
            pygame.K_RIGHT: 'RIGHT',
            pygame.K_RETURN: 'PRESS',
            pygame.K_SPACE: 'PRESS',
            pygame.K_KP_ENTER: 'PRESS',
        }
        
        button = key_map.get(key)
        if button and self._callback:
            self._callback(button)
    
    def cleanup(self):
        pass


class SimulatedHardware:
    """Hardware facade for simulator."""
    
    def __init__(self, surface, scale: int = 4):
        self.lcd = SimulatedLCD(surface, scale)
        self.buttons = SimulatedButtons()
    
    def init(self) -> bool:
        return self.lcd.init() and self.buttons.init()
    
    def start(self, state):
        self.buttons.start_polling()
    
    def wake_display(self, state):
        state.reset_activity()
        return False
    
    def cleanup(self):
        self.lcd.cleanup()
        self.buttons.cleanup()


def handle_button(button_name: str):
    """Global button handler (same as main.py)."""
    if not state.running:
        return
    
    state.render_needed = True
    state.reset_activity()
    
    mode = state.get_current_mode()
    if not mode:
        return
    
    # Dispatch to mode handlers
    handlers = {
        'KEY1': lambda: None,  # Backlight toggle (no-op in sim)
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
            print(f"Button handler error: {e}")
            state.add_alert(f"Error: {str(e)[:30]}", AlertLevel.ERROR)


def main():
    """Run the simulator."""
    print("=" * 60)
    print("  KaliPiMax Desktop Simulator")
    print("=" * 60)
    print()
    print("Controls:")
    print("  1 = KEY1 (backlight)")
    print("  2 = KEY2 (next mode)")
    print("  3 = KEY3 (context action)")
    print("  ↑↓←→ = Joystick navigation")
    print("  Enter/Space = Execute (PRESS)")
    print("  Q/Esc = Quit")
    print()
    
    # Initialise pygame
    pygame.init()
    pygame.display.set_caption("KaliPiMax Simulator")
    
    scale = 4
    screen = pygame.display.set_mode((
        DISPLAY_WIDTH * scale,
        DISPLAY_HEIGHT * scale
    ))
    
    # Create simulated hardware
    hardware = SimulatedHardware(screen, scale)
    hardware.init()
    hardware.buttons.set_global_callback(handle_button)
    
    # Load modes
    modes = get_all_modes()
    state.modes = modes
    state.lcd = hardware.lcd
    
    print(f"Loaded {len(modes)} modes")
    
    # Enter first mode
    if modes:
        modes[0].on_enter()
    
    state.add_alert("Simulator ready", AlertLevel.OK)
    
    # Main loop
    clock = pygame.time.Clock()
    running = True
    
    while running and state.running:
        # Handle pygame events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_q, pygame.K_ESCAPE):
                    running = False
                else:
                    hardware.buttons.handle_key(event.key)
        
        # Render current mode
        mode = state.get_current_mode()
        if mode:
            try:
                img = mode.render()
                if img:
                    hardware.lcd.show_image(img)
            except Exception as e:
                print(f"Render error: {e}")
        
        clock.tick(30)  # 30 FPS
    
    # Cleanup
    state.running = False
    pygame.quit()
    print("\nSimulator closed.")


if __name__ == "__main__":
    main()
