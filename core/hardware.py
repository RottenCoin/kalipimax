#!/usr/bin/env python3
"""
KaliPiMax Hardware Abstraction
LCD display and GPIO button handling.
"""

import time
import threading
from typing import Callable, Dict, Optional

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    import RPi.GPIO as GPIO
    import spidev
    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False
    print("Warning: RPi.GPIO/spidev not available - running in simulation mode")

from PIL import Image

from config import (
    GPIO_PINS, LCD_RST_PIN, LCD_DC_PIN, LCD_CS_PIN, LCD_BL_PIN,
    DISPLAY_WIDTH, DISPLAY_HEIGHT, LCD_X_OFFSET, LCD_Y_OFFSET,
    BUTTON_DEBOUNCE, BACKLIGHT_TIMEOUT
)
from core.logger import log


class LCDDriver:
    """
    Driver for Waveshare 1.44" LCD (ST7735S controller).
    Handles SPI communication and display updates.
    """
    
    # ST7735 commands
    _SWRESET = 0x01
    _SLPOUT = 0x11
    _NORON = 0x13
    _INVOFF = 0x20
    _DISPON = 0x29
    _CASET = 0x2A
    _RASET = 0x2B
    _RAMWR = 0x2C
    _MADCTL = 0x36
    _COLMOD = 0x3A
    
    def __init__(self):
        self._spi = None
        self._width = DISPLAY_WIDTH
        self._height = DISPLAY_HEIGHT
        self._initialised = False
    
    def init(self) -> bool:
        """Initialise the LCD display."""
        if not HARDWARE_AVAILABLE:
            log.info("LCD: Simulation mode")
            self._initialised = True
            return True
        
        try:
            # Set up GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(LCD_RST_PIN, GPIO.OUT)
            GPIO.setup(LCD_DC_PIN, GPIO.OUT)
            GPIO.setup(LCD_CS_PIN, GPIO.OUT)
            GPIO.setup(LCD_BL_PIN, GPIO.OUT)
            
            # Set up SPI
            self._spi = spidev.SpiDev()
            try:
                self._spi.open(0, 0)
            except FileNotFoundError:
                self._spi.open(1, 0)
            
            self._spi.max_speed_hz = 9000000
            self._spi.mode = 0b00
            
            # Hardware reset
            self._reset()
            
            # Initialisation sequence
            self._init_sequence()
            
            # Turn on backlight
            GPIO.output(LCD_BL_PIN, GPIO.HIGH)
            
            self._initialised = True
            log.info("LCD: Initialised successfully")
            return True
            
        except Exception as e:
            log.error(f"LCD: Init failed - {e}")
            return False
    
    def _reset(self):
        """Hardware reset the display."""
        GPIO.output(LCD_RST_PIN, GPIO.HIGH)
        time.sleep(0.01)
        GPIO.output(LCD_RST_PIN, GPIO.LOW)
        time.sleep(0.01)
        GPIO.output(LCD_RST_PIN, GPIO.HIGH)
        time.sleep(0.01)
    
    def _write_cmd(self, cmd: int):
        """Write a command byte."""
        GPIO.output(LCD_DC_PIN, GPIO.LOW)
        GPIO.output(LCD_CS_PIN, GPIO.LOW)
        self._spi.writebytes([cmd])
        GPIO.output(LCD_CS_PIN, GPIO.HIGH)
    
    def _write_data(self, data):
        """Write data bytes."""
        GPIO.output(LCD_DC_PIN, GPIO.HIGH)
        GPIO.output(LCD_CS_PIN, GPIO.LOW)
        if isinstance(data, int):
            self._spi.writebytes([data])
        else:
            # Write in chunks to avoid buffer overflow
            chunk_size = 4096
            for i in range(0, len(data), chunk_size):
                self._spi.writebytes(list(data[i:i + chunk_size]))
        GPIO.output(LCD_CS_PIN, GPIO.HIGH)
    
    def _init_sequence(self):
        """ST7735S initialisation sequence."""
        self._write_cmd(self._SWRESET)
        time.sleep(0.15)
        
        self._write_cmd(self._SLPOUT)
        time.sleep(0.5)
        
        # Set colour mode (16-bit)
        self._write_cmd(self._COLMOD)
        self._write_data(0x05)
        
        # Memory access control (rotation)
        self._write_cmd(self._MADCTL)
        self._write_data(0x60)  # Rotate 90 degrees
        
        self._write_cmd(self._INVOFF)
        self._write_cmd(self._NORON)
        time.sleep(0.01)
        
        self._write_cmd(self._DISPON)
        time.sleep(0.1)
    
    def _set_window(self, x0: int, y0: int, x1: int, y1: int):
        """Set the drawing window."""
        self._write_cmd(self._CASET)
        self._write_data(0x00)
        self._write_data(x0 + LCD_X_OFFSET)
        self._write_data(0x00)
        self._write_data(x1 + LCD_X_OFFSET)
        
        self._write_cmd(self._RASET)
        self._write_data(0x00)
        self._write_data(y0 + LCD_Y_OFFSET)
        self._write_data(0x00)
        self._write_data(y1 + LCD_Y_OFFSET)
        
        self._write_cmd(self._RAMWR)
    
    def show_image(self, image: Image.Image):
        """Display a PIL Image on the LCD."""
        if not self._initialised:
            return
        
        if not HARDWARE_AVAILABLE:
            return
        
        # Ensure correct size and mode
        if image.size != (self._width, self._height):
            image = image.resize((self._width, self._height))
        
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Convert to RGB565
        if NUMPY_AVAILABLE:
            pixels = np.frombuffer(image.tobytes(), dtype=np.uint8).reshape(-1, 3)
            r, g, b = pixels[:, 0].astype(np.uint16), pixels[:, 1].astype(np.uint16), pixels[:, 2].astype(np.uint16)
            rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            buffer = rgb565.astype('>u2').tobytes()  # Big-endian uint16
        else:
            pixels = image.tobytes()
            buffer = []
            for i in range(0, len(pixels), 3):
                r, g, b = pixels[i], pixels[i+1], pixels[i+2]
                rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                buffer.append(rgb565 >> 8)
                buffer.append(rgb565 & 0xFF)
            buffer = bytes(buffer)
        
        self._set_window(0, 0, self._width - 1, self._height - 1)
        self._write_data(buffer)
    
    def clear(self, colour: tuple = (0, 0, 0)):
        """Clear the display to a solid colour."""
        img = Image.new('RGB', (self._width, self._height), colour)
        self.show_image(img)
    
    def set_backlight(self, on: bool):
        """Turn backlight on or off."""
        if HARDWARE_AVAILABLE:
            GPIO.output(LCD_BL_PIN, GPIO.HIGH if on else GPIO.LOW)
    
    def cleanup(self):
        """Clean up resources."""
        if self._spi:
            self._spi.close()


class ButtonHandler:
    """
    Handles physical button input with debouncing and event dispatch.
    """
    
    def __init__(self):
        self._callbacks: Dict[str, Callable] = {}
        self._global_callback: Optional[Callable] = None
        self._last_state: Dict[str, int] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def init(self) -> bool:
        """Initialise GPIO for buttons."""
        if not HARDWARE_AVAILABLE:
            log.info("Buttons: Simulation mode")
            return True
        
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            
            for name, pin in GPIO_PINS.items():
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                self._last_state[name] = GPIO.HIGH
                log.debug(f"  Button {name:6} = GPIO {pin:2}")
            
            log.info("Buttons: Initialised successfully")
            return True
            
        except Exception as e:
            log.error(f"Buttons: Init failed - {e}")
            return False
    
    def set_callback(self, button_name: str, callback: Callable):
        """Register a callback for a button press."""
        self._callbacks[button_name] = callback
    
    def set_global_callback(self, callback: Callable):
        """Register a callback that receives all button events."""
        self._global_callback = callback
    
    def start_polling(self):
        """Start the button polling thread."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        log.info("Button polling started")
    
    def stop_polling(self):
        """Stop the button polling thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
    
    def _poll_loop(self):
        """Main polling loop (runs in separate thread)."""
        while self._running:
            try:
                if not HARDWARE_AVAILABLE:
                    time.sleep(0.1)
                    continue
                
                for name, pin in GPIO_PINS.items():
                    current = GPIO.input(pin)
                    
                    # Detect falling edge (button press)
                    if self._last_state[name] == GPIO.HIGH and current == GPIO.LOW:
                        self._handle_press(name)
                        time.sleep(BUTTON_DEBOUNCE)
                        
                        # Wait for release with timeout
                        timeout = 50
                        while GPIO.input(pin) == GPIO.LOW and self._running and timeout > 0:
                            time.sleep(BUTTON_DEBOUNCE)
                            timeout -= 1
                    
                    self._last_state[name] = current
                
                time.sleep(0.005)
                
            except Exception as e:
                log.error(f"Button poll error: {e}")
                time.sleep(0.1)
    
    def _handle_press(self, button_name: str):
        """Handle a button press event."""
        # Call global callback if set
        if self._global_callback:
            try:
                self._global_callback(button_name)
            except Exception as e:
                log.error(f"Global callback error: {e}")
        
        # Call specific callback if set
        if button_name in self._callbacks:
            try:
                self._callbacks[button_name]()
            except Exception as e:
                log.error(f"Button callback error: {e}")
    
    def cleanup(self):
        """Clean up resources."""
        self.stop_polling()


class Hardware:
    """
    Main hardware interface combining LCD and buttons.
    """
    
    def __init__(self):
        self.lcd = LCDDriver()
        self.buttons = ButtonHandler()
        self._backlight_thread: Optional[threading.Thread] = None
        self._backlight_running = False
    
    def init(self) -> bool:
        """Initialise all hardware."""
        log.info("=" * 50)
        log.info("Initialising hardware...")
        log.info("=" * 50)
        
        lcd_ok = self.lcd.init()
        btn_ok = self.buttons.init()
        
        if lcd_ok and btn_ok:
            log.info("=" * 50)
            log.info("Hardware initialisation complete")
            log.info("=" * 50)
            return True
        
        return False
    
    def start(self, state):
        """Start hardware services."""
        self.buttons.start_polling()
        self._start_backlight_manager(state)
    
    def _start_backlight_manager(self, state):
        """Start the backlight timeout manager."""
        self._backlight_running = True
        self._backlight_thread = threading.Thread(
            target=self._backlight_loop,
            args=(state,),
            daemon=True
        )
        self._backlight_thread.start()
        log.info("Backlight manager started")
    
    def _backlight_loop(self, state):
        """Manage backlight timeout."""
        while self._backlight_running:
            try:
                idle_time = time.time() - state.last_activity
                
                if idle_time > BACKLIGHT_TIMEOUT and state.backlight_on:
                    state.backlight_on = False
                    self.lcd.set_backlight(False)
                
                time.sleep(1)
                
            except Exception as e:
                log.error(f"Backlight manager error: {e}")
                time.sleep(5)
    
    def wake_display(self, state):
        """Wake the display if it's off."""
        if not state.backlight_on:
            state.backlight_on = True
            self.lcd.set_backlight(True)
            state.reset_activity()
            return True
        state.reset_activity()
        return False
    
    def cleanup(self):
        """Clean up all hardware resources."""
        log.info("Cleaning up hardware...")
        self._backlight_running = False
        self.buttons.cleanup()
        
        try:
            self.lcd.clear()
            self.lcd.set_backlight(False)
            self.lcd.cleanup()
        except Exception:
            pass
        
        # GPIO cleanup must run even if LCD cleanup fails above
        if HARDWARE_AVAILABLE:
            try:
                GPIO.cleanup()
            except Exception:
                pass


# Singleton instance
hardware = Hardware()
