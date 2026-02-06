#!/usr/bin/env python3
"""
KaliPiMax Renderer and Menu Tests
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock hardware modules
from unittest.mock import MagicMock
sys.modules['RPi'] = MagicMock()
sys.modules['RPi.GPIO'] = MagicMock()
sys.modules['spidev'] = MagicMock()

import pytest
from PIL import Image

from config import DISPLAY_WIDTH, DISPLAY_HEIGHT, COLOURS, MENU_VISIBLE_ITEMS
from ui.renderer import Canvas, MenuRenderer, Fonts, get_colour_for_percent, truncate


class TestCanvas:
    """Tests for Canvas class."""
    
    def test_canvas_creation(self):
        """Test canvas is created with correct dimensions."""
        canvas = Canvas()
        
        assert canvas.width == DISPLAY_WIDTH
        assert canvas.height == DISPLAY_HEIGHT
        assert canvas.image.size == (DISPLAY_WIDTH, DISPLAY_HEIGHT)
        assert canvas.image.mode == 'RGB'
    
    def test_canvas_custom_size(self):
        """Test canvas with custom dimensions."""
        canvas = Canvas(width=64, height=64)
        
        assert canvas.width == 64
        assert canvas.height == 64
        assert canvas.image.size == (64, 64)
    
    def test_canvas_clear(self):
        """Test canvas clear."""
        canvas = Canvas()
        
        # Draw something
        canvas.rect(0, 0, 50, 50, fill='error')
        
        # Clear
        canvas.clear()
        
        # Check pixel at origin is background colour
        pixel = canvas.image.getpixel((10, 10))
        assert pixel == COLOURS['bg']
    
    def test_canvas_text(self):
        """Test text rendering doesn't crash."""
        canvas = Canvas()
        
        # Should not raise
        canvas.text(10, 10, "Hello World", colour='text', font='small')
    
    def test_canvas_rect(self):
        """Test rectangle rendering."""
        canvas = Canvas()
        
        canvas.rect(10, 10, 50, 50, fill='error')
        
        # Check centre of rectangle has fill colour
        pixel = canvas.image.getpixel((30, 30))
        assert pixel == COLOURS['error']
    
    def test_canvas_progress_bar(self):
        """Test progress bar rendering."""
        canvas = Canvas()
        
        # Should not raise
        canvas.progress_bar(10, 10, 100, 10, 50, fill_colour='ok')
        canvas.progress_bar(10, 30, 100, 10, 0, fill_colour='ok')
        canvas.progress_bar(10, 50, 100, 10, 100, fill_colour='ok')
    
    def test_canvas_header(self):
        """Test header rendering returns Y position."""
        canvas = Canvas()
        
        y = canvas.header("TEST HEADER")
        
        assert isinstance(y, int)
        assert y > 0
    
    def test_canvas_get_image(self):
        """Test get_image returns PIL Image."""
        canvas = Canvas()
        
        img = canvas.get_image()
        
        assert isinstance(img, Image.Image)
        assert img.size == (DISPLAY_WIDTH, DISPLAY_HEIGHT)


class TestMenuRenderer:
    """Tests for MenuRenderer class."""
    
    def test_menu_creation(self):
        """Test menu renderer creation."""
        items = [
            {'icon': '●', 'text': 'Item 1'},
            {'icon': '●', 'text': 'Item 2'},
        ]
        
        menu = MenuRenderer(items)
        
        assert menu.selected == 0
        assert len(menu.items) == 2
    
    def test_menu_selection_bounds(self):
        """Test selection stays within bounds."""
        items = [{'text': f'Item {i}'} for i in range(5)]
        menu = MenuRenderer(items)
        
        # Can't go below 0
        menu.set_selection(-5)
        assert menu.selected == 0
        
        # Can't go above max
        menu.set_selection(100)
        assert menu.selected == 4
    
    def test_menu_move_selection(self):
        """Test moving selection."""
        items = [{'text': f'Item {i}'} for i in range(5)]
        menu = MenuRenderer(items)
        
        assert menu.selected == 0
        
        menu.move_selection(1)
        assert menu.selected == 1
        
        menu.move_selection(2)
        assert menu.selected == 3
        
        menu.move_selection(-2)
        assert menu.selected == 1
    
    def test_menu_scrolling(self):
        """Test menu scrolls when selection moves."""
        items = [{'text': f'Item {i}'} for i in range(15)]
        menu = MenuRenderer(items, visible_count=7)
        
        # Initially at top
        assert menu._scroll_offset == 0
        
        # Move down past visible area
        menu.set_selection(10)
        
        # Should have scrolled
        assert menu._scroll_offset > 0
        assert menu.selected >= menu._scroll_offset
        assert menu.selected < menu._scroll_offset + 7
    
    def test_menu_get_selected_item(self):
        """Test getting selected item."""
        items = [
            {'text': 'Item 1', 'value': 1},
            {'text': 'Item 2', 'value': 2},
        ]
        menu = MenuRenderer(items)
        
        item = menu.get_selected_item()
        assert item['value'] == 1
        
        menu.set_selection(1)
        item = menu.get_selected_item()
        assert item['value'] == 2
    
    def test_menu_render(self):
        """Test menu renders without error."""
        items = [
            {'icon': '●', 'text': 'Item 1'},
            {'icon': '●', 'text': 'Item 2'},
            {'icon': '●', 'text': 'Item 3'},
        ]
        menu = MenuRenderer(items)
        canvas = Canvas()
        
        # Should not raise
        y = menu.render(canvas)
        
        assert isinstance(y, int)
        assert y > menu.start_y


class TestFonts:
    """Tests for font loading."""
    
    def test_font_cache(self):
        """Test fonts are cached."""
        font1 = Fonts.get('small')
        font2 = Fonts.get('small')
        
        assert font1 is font2
    
    def test_font_sizes(self):
        """Test different font sizes load."""
        # Should not raise
        Fonts.title()
        Fonts.large()
        Fonts.medium()
        Fonts.small()
        Fonts.tiny()


class TestHelperFunctions:
    """Tests for helper functions."""
    
    def test_get_colour_for_percent_ok(self):
        """Test colour for low values."""
        colour = get_colour_for_percent(25)
        assert colour == 'ok'
    
    def test_get_colour_for_percent_warning(self):
        """Test colour for medium values."""
        colour = get_colour_for_percent(60)
        assert colour == 'warning'
    
    def test_get_colour_for_percent_error(self):
        """Test colour for high values."""
        colour = get_colour_for_percent(90)
        assert colour == 'error'
    
    def test_get_colour_custom_thresholds(self):
        """Test colour with custom thresholds."""
        colour = get_colour_for_percent(45, thresholds=(40, 60))
        assert colour == 'warning'
        
        colour = get_colour_for_percent(65, thresholds=(40, 60))
        assert colour == 'error'
    
    def test_truncate_short_string(self):
        """Test truncate with short string."""
        result = truncate("Hello", 10)
        assert result == "Hello"
    
    def test_truncate_long_string(self):
        """Test truncate with long string."""
        result = truncate("Hello World This Is Long", 10)
        assert len(result) == 10
        assert result.endswith("…")
    
    def test_truncate_exact_length(self):
        """Test truncate with exact length string."""
        result = truncate("Hello", 5)
        assert result == "Hello"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
