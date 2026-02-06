#!/usr/bin/env python3
"""
KaliPiMax UI Rendering
Font loading, drawing utilities, and common UI components.
"""

from PIL import Image, ImageDraw, ImageFont
from typing import Optional, List, Tuple

from config import (
    DISPLAY_WIDTH, DISPLAY_HEIGHT, COLOURS, FONT_PATH, FONT_SIZES,
    MENU_VISIBLE_ITEMS, SCROLL_INDICATOR_WIDTH
)


class Fonts:
    """Font loader and cache."""
    
    _cache = {}
    
    @classmethod
    def get(cls, size_name: str) -> ImageFont.FreeTypeFont:
        """Get a font by size name (title, large, medium, small, tiny)."""
        if size_name not in cls._cache:
            size = FONT_SIZES.get(size_name, 10)
            try:
                # Try bold for title/large
                if size_name in ("title", "large"):
                    cls._cache[size_name] = ImageFont.truetype(
                        f"{FONT_PATH}-Bold.ttf", size
                    )
                else:
                    cls._cache[size_name] = ImageFont.truetype(
                        f"{FONT_PATH}.ttf", size
                    )
            except OSError:
                print(f"Warning: Could not load font for {size_name}, using default")
                cls._cache[size_name] = ImageFont.load_default()
        
        return cls._cache[size_name]
    
    @classmethod
    def title(cls):
        return cls.get("title")
    
    @classmethod
    def large(cls):
        return cls.get("large")
    
    @classmethod
    def medium(cls):
        return cls.get("medium")
    
    @classmethod
    def small(cls):
        return cls.get("small")
    
    @classmethod
    def tiny(cls):
        return cls.get("tiny")


class Canvas:
    """
    Convenience wrapper around PIL Image/ImageDraw.
    Provides high-level drawing methods with colour shortcuts.
    """
    
    def __init__(self, width: int = DISPLAY_WIDTH, height: int = DISPLAY_HEIGHT):
        self.width = width
        self.height = height
        self.image = Image.new('RGB', (width, height), COLOURS['bg'])
        self.draw = ImageDraw.Draw(self.image)
    
    def clear(self, colour: str = 'bg'):
        """Clear canvas to a colour."""
        self.draw.rectangle((0, 0, self.width, self.height), fill=COLOURS.get(colour, colour))
    
    def text(
        self,
        x: int,
        y: int,
        text: str,
        colour: str = 'text',
        font: str = 'small'
    ):
        """Draw text at position."""
        self.draw.text(
            (x, y),
            text,
            font=Fonts.get(font),
            fill=COLOURS.get(colour, colour)
        )
    
    def rect(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        fill: Optional[str] = None,
        outline: Optional[str] = None
    ):
        """Draw a rectangle."""
        self.draw.rectangle(
            (x1, y1, x2, y2),
            fill=COLOURS.get(fill, fill) if fill else None,
            outline=COLOURS.get(outline, outline) if outline else None
        )
    
    def line(self, x1: int, y1: int, x2: int, y2: int, colour: str = 'text_dim'):
        """Draw a line."""
        self.draw.line((x1, y1, x2, y2), fill=COLOURS.get(colour, colour))
    
    def progress_bar(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        percent: float,
        fill_colour: str = 'ok',
        bg_colour: str = 'bg'
    ):
        """Draw a progress bar."""
        # Background
        self.rect(x, y, x + width, y + height, outline='text_dim')
        
        # Fill
        fill_width = int(width * min(100, max(0, percent)) / 100)
        if fill_width > 0:
            self.rect(x, y, x + fill_width, y + height, fill=fill_colour)
    
    def header(self, title: str, colour: str = 'title'):
        """Draw a standard header."""
        self.text(2, 2, title, colour=colour, font='title')
        return 18  # Return Y position after header
    
    def status_bar(self, text: str, colour: str = 'highlight'):
        """Draw a status bar at top of screen."""
        self.rect(0, 0, self.width, 16, fill='bg_warning')
        self.text(2, 2, text, colour=colour, font='small')
        return 18
    
    def footer(self, text: str):
        """Draw footer text at bottom."""
        self.text(2, self.height - 10, text, colour='text_dim', font='tiny')
    
    def get_image(self) -> Image.Image:
        """Get the PIL Image."""
        return self.image


class MenuRenderer:
    """
    Renders scrollable menus with selection highlight.
    """
    
    def __init__(
        self,
        items: List[dict],
        selected: int = 0,
        visible_count: int = MENU_VISIBLE_ITEMS,
        start_y: int = 20
    ):
        self.items = items
        self.selected = selected
        self.visible_count = visible_count
        self.start_y = start_y
        self._scroll_offset = 0
    
    def set_selection(self, index: int):
        """Set the selected item index."""
        self.selected = max(0, min(len(self.items) - 1, index))
        self._update_scroll()
    
    def move_selection(self, delta: int):
        """Move selection by delta (positive = down, negative = up)."""
        self.set_selection(self.selected + delta)
    
    def _update_scroll(self):
        """Update scroll offset to keep selection visible."""
        if self.selected < self._scroll_offset:
            self._scroll_offset = self.selected
        elif self.selected >= self._scroll_offset + self.visible_count:
            self._scroll_offset = self.selected - self.visible_count + 1
    
    def render(self, canvas: Canvas) -> int:
        """
        Render the menu on the canvas.
        
        Returns the Y position after the menu.
        """
        y = self.start_y
        item_height = 15
        
        # Render visible items
        for i in range(self.visible_count):
            idx = self._scroll_offset + i
            if idx >= len(self.items):
                break
            
            item = self.items[idx]
            is_selected = (idx == self.selected)
            
            # Selection highlight
            if is_selected:
                canvas.rect(0, y, DISPLAY_WIDTH - SCROLL_INDICATOR_WIDTH - 1, y + item_height - 1,
                           fill='bg_selected')
            
            # Icon
            icon = item.get('icon', '>')
            icon_colour = 'highlight' if is_selected else 'info'
            canvas.text(2, y + 1, icon, colour=icon_colour, font='medium')
            
            # Text
            text = item.get('text', '')[:18]
            text_colour = 'text' if is_selected else 'text_dim'
            canvas.text(14, y + 2, text, colour=text_colour, font='small')
            
            # Status indicator (optional)
            status = item.get('status')
            if status:
                status_colour = item.get('status_colour', 'ok')
                canvas.text(115, y + 2, status, colour=status_colour, font='tiny')
            
            y += item_height
        
        # Scrollbar
        if len(self.items) > self.visible_count:
            self._draw_scrollbar(canvas)
        
        return y
    
    def _draw_scrollbar(self, canvas: Canvas):
        """Draw the scroll indicator."""
        bar_x = DISPLAY_WIDTH - SCROLL_INDICATOR_WIDTH
        bar_y = self.start_y
        bar_height = self.visible_count * 15
        
        # Background
        canvas.rect(bar_x, bar_y, DISPLAY_WIDTH - 1, bar_y + bar_height - 1,
                   fill='scrollbar_bg')
        
        # Thumb
        total_items = len(self.items)
        thumb_height = max(8, int(bar_height * self.visible_count / total_items))
        thumb_pos = bar_y + int(
            (bar_height - thumb_height) * self._scroll_offset / (total_items - self.visible_count)
        )
        
        canvas.rect(bar_x, thumb_pos, DISPLAY_WIDTH - 1, thumb_pos + thumb_height,
                   fill='scrollbar_thumb')
    
    def get_selected_item(self) -> Optional[dict]:
        """Get the currently selected item."""
        if 0 <= self.selected < len(self.items):
            return self.items[self.selected]
        return None


def get_colour_for_percent(percent: float, thresholds: Tuple[int, int] = (50, 80)) -> str:
    """Get a colour name based on a percentage value."""
    if percent >= thresholds[1]:
        return 'error'
    elif percent >= thresholds[0]:
        return 'warning'
    return 'ok'


def truncate(text: str, max_len: int) -> str:
    """Truncate text with ellipsis if too long."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "…"
