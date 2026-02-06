#!/usr/bin/env python3
"""
KaliPiMax Alerts Mode
View system alerts and event log.
"""

from PIL import Image

from ui.base_mode import BaseMode
from ui.renderer import Canvas
from core.state import state, AlertLevel
from config import COLOURS


# Map AlertLevel to display colour
LEVEL_COLOURS = {
    AlertLevel.INFO: 'info',
    AlertLevel.OK: 'ok',
    AlertLevel.WARNING: 'warning',
    AlertLevel.ERROR: 'error',
    AlertLevel.CRITICAL: 'error',
}


class AlertsMode(BaseMode):
    """
    Alerts display mode.
    
    Shows recent system alerts with timestamps and severity colours.
    """
    
    def __init__(self):
        super().__init__("ALERTS", "⚠")
        self._scroll_offset = 0
        self._visible_count = 8
    
    def on_enter(self):
        """Reset scroll to show latest alerts."""
        self._scroll_to_end()
    
    def _scroll_to_end(self):
        """Scroll to show the most recent alerts."""
        total = len(state.alerts)
        if total > self._visible_count:
            self._scroll_offset = total - self._visible_count
        else:
            self._scroll_offset = 0
    
    def on_up(self):
        """Scroll up in alert history."""
        if self._scroll_offset > 0:
            self._scroll_offset -= 1
            state.render_needed = True
    
    def on_down(self):
        """Scroll down in alert history."""
        total = len(state.alerts)
        max_offset = max(0, total - self._visible_count)
        if self._scroll_offset < max_offset:
            self._scroll_offset += 1
            state.render_needed = True
    
    def on_key3(self):
        """Clear all alerts."""
        state.clear_alerts()
        self._scroll_offset = 0
    
    def on_press(self):
        """Jump to latest alerts."""
        self._scroll_to_end()
        state.render_needed = True
    
    def render(self) -> Image.Image:
        canvas = self._create_canvas()
        
        alerts = state.alerts
        total = len(alerts)
        
        y = 2
        
        # Header with count
        canvas.text(2, y, "ALERTS", colour='error', font='title')
        canvas.text(70, y + 2, f"({total})", colour='text_dim', font='small')
        y += 16
        
        if not alerts:
            canvas.text(20, 60, "No alerts", colour='text_dim', font='medium')
            return canvas.get_image()
        
        # Visible alerts
        visible_alerts = alerts[self._scroll_offset:self._scroll_offset + self._visible_count]
        
        for alert in visible_alerts:
            # Timestamp
            canvas.text(2, y, alert.time_str, colour='text_dim', font='tiny')
            y += 8
            
            # Message with level colour
            colour = LEVEL_COLOURS.get(alert.level, 'text')
            msg = alert.message[:22]  # Truncate long messages
            canvas.text(2, y, msg, colour=colour, font='small')
            y += 12
        
        # Scroll indicator
        if total > self._visible_count:
            # Show position
            pos_text = f"{self._scroll_offset + 1}-{min(self._scroll_offset + self._visible_count, total)}/{total}"
            canvas.text(80, 2, pos_text, colour='text_dim', font='tiny')
            
            # Draw scrollbar
            bar_x = 125
            bar_y = 18
            bar_height = 90
            
            canvas.rect(bar_x, bar_y, 127, bar_y + bar_height, fill='scrollbar_bg')
            
            thumb_height = max(10, int(bar_height * self._visible_count / total))
            max_offset = total - self._visible_count
            thumb_pos = bar_y + int((bar_height - thumb_height) * self._scroll_offset / max_offset) if max_offset > 0 else bar_y
            
            canvas.rect(bar_x, thumb_pos, 127, thumb_pos + thumb_height, fill='scrollbar_thumb')
        
        canvas.footer("↑↓:Scroll K3:Clear ●:Latest")
        
        return canvas.get_image()
