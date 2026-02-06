#!/usr/bin/env python3
"""
KaliPiMax Base Mode
Abstract base class for all operational modes.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Callable
from PIL import Image

from config import DISPLAY_WIDTH, DISPLAY_HEIGHT, MENU_VISIBLE_ITEMS
from ui.renderer import Canvas, MenuRenderer, Fonts
from core.state import state


class BaseMode(ABC):
    """
    Abstract base class for operational modes.
    
    Each mode represents a screen/functionality (System, Nmap, WiFi, etc.)
    and handles its own rendering and button input.
    """
    
    def __init__(self, name: str, icon: str = "●"):
        self.name = name
        self.icon = icon
        self._menu: Optional[MenuRenderer] = None
        self._menu_items: List[dict] = []
    
    # -------------------------------------------------------------------------
    # Lifecycle methods
    # -------------------------------------------------------------------------
    
    def on_enter(self):
        """
        Called when this mode becomes active.
        Override to initialise mode-specific state.
        """
        if self._menu_items:
            self._menu = MenuRenderer(
                items=self._menu_items,
                selected=0,
                visible_count=MENU_VISIBLE_ITEMS
            )
    
    def on_exit(self):
        """
        Called when leaving this mode.
        Override to clean up mode-specific state.
        """
        pass
    
    # -------------------------------------------------------------------------
    # Button handlers - override in subclasses
    # -------------------------------------------------------------------------
    
    def on_key1(self):
        """
        KEY1 button press.
        Default: Toggle backlight.
        Override for mode-specific behaviour (e.g. LootMode view switch).
        """
        from core.hardware import hardware
        new_state = not state.backlight_on
        hardware.lcd.set_backlight(new_state)
        state.backlight_on = new_state
    
    def on_key2(self):
        """
        KEY2 button press.
        Default: Next mode (handled globally).
        """
        state.change_mode(1)
    
    def on_key3(self):
        """
        KEY3 button press.
        Default: Mode-specific action or cancel payload.
        Override in subclasses.
        """
        pass
    
    def on_up(self):
        """
        Joystick UP.
        Default: Move menu selection up.
        """
        if self._menu:
            self._menu.move_selection(-1)
            state.render_needed = True
    
    def on_down(self):
        """
        Joystick DOWN.
        Default: Move menu selection down.
        """
        if self._menu:
            self._menu.move_selection(1)
            state.render_needed = True
    
    def on_left(self):
        """
        Joystick LEFT.
        Default: Previous mode.
        """
        state.change_mode(-1)
    
    def on_right(self):
        """
        Joystick RIGHT.
        Default: Next mode.
        """
        state.change_mode(1)
    
    def on_press(self):
        """
        Joystick PRESS (centre button).
        Default: Execute selected menu item.
        Override for custom behaviour.
        """
        if self._menu:
            item = self._menu.get_selected_item()
            if item and 'action' in item and callable(item['action']):
                item['action']()
    
    # -------------------------------------------------------------------------
    # Rendering
    # -------------------------------------------------------------------------
    
    @abstractmethod
    def render(self) -> Image.Image:
        """
        Render the mode's display.
        
        Must be implemented by all subclasses.
        Should be fast and non-blocking.
        
        Returns:
            PIL Image to display on LCD.
        """
        pass
    
    def _create_canvas(self) -> Canvas:
        """Create a new canvas for rendering."""
        return Canvas(DISPLAY_WIDTH, DISPLAY_HEIGHT)
    
    def _render_header(self, canvas: Canvas, title: Optional[str] = None) -> int:
        """
        Render the standard header.
        
        Returns Y position after header.
        """
        y = 2
        
        # Show payload status bar if running
        if state.is_payload_running():
            payload = state.current_payload
            if payload:
                elapsed = int(payload.elapsed)
                status_text = f"⚡ {payload.name[:12]} ({elapsed}s)"
                y = canvas.status_bar(status_text)
        
        # Mode title
        title = title or self.name
        canvas.text(2, y, title, colour='title', font='title')
        
        return y + 16
    
    def _render_menu(self, canvas: Canvas, start_y: int = 20) -> int:
        """
        Render the menu if present.
        
        Returns Y position after menu.
        """
        if self._menu:
            self._menu.start_y = start_y
            return self._menu.render(canvas)
        return start_y
    
    def _render_footer(self, canvas: Canvas, text: str):
        """Render footer hint text."""
        canvas.footer(text)
    
    # -------------------------------------------------------------------------
    # Menu helpers
    # -------------------------------------------------------------------------
    
    def _set_menu_items(self, items: List[dict]):
        """
        Set the menu items for this mode.
        
        Each item is a dict with:
            - text: Display text
            - action: Callable to execute on press
            - icon: Optional icon character (default '●')
            - status: Optional status text
            - status_colour: Optional status colour
        """
        self._menu_items = items
        if self._menu:
            self._menu.items = items
            self._menu.set_selection(0)
    
    def _get_selected_index(self) -> int:
        """Get the currently selected menu index."""
        if self._menu:
            return self._menu.selected
        return 0
    
    def _refresh_menu(self):
        """Refresh the menu (e.g., after items change)."""
        if self._menu_items:
            current_selection = self._get_selected_index()
            self._menu = MenuRenderer(
                items=self._menu_items,
                selected=min(current_selection, len(self._menu_items) - 1),
                visible_count=MENU_VISIBLE_ITEMS
            )


class InfoMode(BaseMode):
    """
    Base class for information display modes (no menu).
    Shows data with optional refresh.
    """
    
    def __init__(self, name: str, icon: str = "ℹ"):
        super().__init__(name, icon)
        self._last_refresh = 0
        self._refresh_interval = 2.0  # Seconds
        self._cached_data = {}
    
    def on_enter(self):
        """Refresh data when entering mode."""
        self._refresh_data()
    
    def on_key3(self):
        """Force refresh on KEY3."""
        self._refresh_data()
        state.render_needed = True
    
    def _refresh_data(self):
        """
        Refresh the displayed data.
        Override to fetch new data.
        """
        import time
        self._last_refresh = time.time()
    
    def _should_refresh(self) -> bool:
        """Check if data should be refreshed."""
        import time
        return time.time() - self._last_refresh > self._refresh_interval


class MenuMode(BaseMode):
    """
    Base class for menu-based modes.
    Provides standard menu rendering and navigation.
    """
    
    def __init__(self, name: str, icon: str = "●"):
        super().__init__(name, icon)
    
    def render(self) -> Image.Image:
        """Standard menu mode render."""
        canvas = self._create_canvas()
        
        y = self._render_header(canvas)
        y = self._render_menu(canvas, start_y=y)
        
        # Footer with controls hint
        self._render_footer(canvas, "↑↓:Select ●:Execute")
        
        return canvas.get_image()
