#!/usr/bin/env python3
"""
KaliPiMax Loot Mode
Browse and manage captured data files.
"""

import os
import time
from pathlib import Path
from PIL import Image

from ui.base_mode import BaseMode
from ui.renderer import Canvas
from core.state import state, AlertLevel
from config import LOOT_DIR, LOOT_SUBDIRS


def get_file_size_str(size: int) -> str:
    """Format file size to human-readable."""
    for unit in ['B', 'K', 'M', 'G']:
        if size < 1024:
            return f"{size:.0f}{unit}"
        size /= 1024
    return f"{size:.0f}T"


def get_loot_stats() -> dict:
    """Get statistics for loot directories."""
    stats = {}
    
    for subdir in LOOT_SUBDIRS:
        path = LOOT_DIR / subdir
        if path.exists():
            files = list(path.glob('*'))
            total_size = sum(f.stat().st_size for f in files if f.is_file())
            stats[subdir] = {
                'count': len([f for f in files if f.is_file()]),
                'size': total_size,
            }
        else:
            stats[subdir] = {'count': 0, 'size': 0}
    
    return stats


def get_recent_files(limit: int = 10) -> list:
    """Get most recently modified loot files."""
    files = []
    
    for subdir in LOOT_SUBDIRS:
        path = LOOT_DIR / subdir
        if path.exists():
            for f in path.glob('*'):
                if f.is_file():
                    files.append({
                        'path': f,
                        'name': f.name,
                        'category': subdir,
                        'size': f.stat().st_size,
                        'mtime': f.stat().st_mtime,
                    })
    
    # Sort by modification time, newest first
    files.sort(key=lambda x: x['mtime'], reverse=True)
    return files[:limit]


def delete_old_files(days: int = 7) -> int:
    """Delete files older than specified days."""
    cutoff = time.time() - (days * 86400)
    deleted = 0
    
    for subdir in LOOT_SUBDIRS:
        path = LOOT_DIR / subdir
        if path.exists():
            for f in path.glob('*'):
                if f.is_file() and f.stat().st_mtime < cutoff:
                    try:
                        f.unlink()
                        deleted += 1
                    except Exception:
                        pass
    
    return deleted


class LootMode(BaseMode):
    """
    Loot browser mode.
    
    View and manage captured data organised by category.
    """
    
    VIEW_STATS = 0
    VIEW_FILES = 1
    
    def __init__(self):
        super().__init__("LOOT", "📁")
        
        self._view = self.VIEW_STATS
        self._stats = {}
        self._files = []
        self._selected = 0
        self._scroll_offset = 0
        self._visible_count = 6
        self._last_refresh = 0
    
    def on_enter(self):
        self._refresh_data()
        self._selected = 0
        self._scroll_offset = 0
    
    def _refresh_data(self):
        """Refresh loot statistics and file list."""
        self._stats = get_loot_stats()
        self._files = get_recent_files(20)
        self._last_refresh = time.time()
        
        # Adjust selection bounds
        max_items = len(LOOT_SUBDIRS) if self._view == self.VIEW_STATS else len(self._files)
        self._selected = min(self._selected, max(0, max_items - 1))
    
    def on_up(self):
        if self._selected > 0:
            self._selected -= 1
            self._update_scroll()
            state.render_needed = True
    
    def on_down(self):
        max_items = len(LOOT_SUBDIRS) if self._view == self.VIEW_STATS else len(self._files)
        if self._selected < max_items - 1:
            self._selected += 1
            self._update_scroll()
            state.render_needed = True
    
    def _update_scroll(self):
        if self._selected < self._scroll_offset:
            self._scroll_offset = self._selected
        elif self._selected >= self._scroll_offset + self._visible_count:
            self._scroll_offset = self._selected - self._visible_count + 1
    
    def on_press(self):
        """Switch view or show file info."""
        if self._view == self.VIEW_STATS:
            self._view = self.VIEW_FILES
            self._selected = 0
            self._scroll_offset = 0
        else:
            # Show file info
            if self._files and self._selected < len(self._files):
                f = self._files[self._selected]
                state.add_alert(f"{f['category']}/{f['name']}", AlertLevel.INFO)
        state.render_needed = True
    
    def on_key1(self):
        """Toggle between views."""
        self._view = self.VIEW_FILES if self._view == self.VIEW_STATS else self.VIEW_STATS
        self._selected = 0
        self._scroll_offset = 0
        state.render_needed = True
    
    def on_key3(self):
        """Cleanup old files."""
        deleted = delete_old_files(7)
        state.add_alert(f"Deleted {deleted} files (>7d)", AlertLevel.OK)
        self._refresh_data()
        state.render_needed = True
    
    def render(self) -> Image.Image:
        canvas = self._create_canvas()
        
        # Auto-refresh every 10s
        if time.time() - self._last_refresh > 10:
            self._refresh_data()
        
        y = 2
        
        # Header
        view_name = "Stats" if self._view == self.VIEW_STATS else "Files"
        canvas.text(2, y, f"LOOT [{view_name}]", colour='title', font='title')
        y += 16
        
        if self._view == self.VIEW_STATS:
            y = self._render_stats(canvas, y)
        else:
            y = self._render_files(canvas, y)
        
        canvas.footer("K1:View K3:Cleanup ●:Detail")
        
        return canvas.get_image()
    
    def _render_stats(self, canvas: Canvas, y: int) -> int:
        """Render category statistics."""
        total_files = 0
        total_size = 0
        
        for i, subdir in enumerate(LOOT_SUBDIRS):
            is_selected = (i == self._selected)
            stat = self._stats.get(subdir, {'count': 0, 'size': 0})
            
            total_files += stat['count']
            total_size += stat['size']
            
            if is_selected:
                canvas.rect(0, y - 1, 127, y + 11, fill='bg_selected')
            
            # Category name
            text_colour = 'highlight' if is_selected else 'text'
            canvas.text(2, y, f"{subdir[:8]:8}", colour=text_colour, font='small')
            
            # Count and size
            count_colour = 'ok' if stat['count'] > 0 else 'text_dim'
            canvas.text(65, y, f"{stat['count']:3}", colour=count_colour, font='small')
            canvas.text(90, y, get_file_size_str(stat['size']), colour='text_dim', font='tiny')
            
            y += 12
        
        # Total
        y += 2
        canvas.line(2, y, 126, y, colour='text_dim')
        y += 4
        canvas.text(2, y, f"Total: {total_files} files", colour='info', font='small')
        canvas.text(80, y, get_file_size_str(total_size), colour='text_dim', font='small')
        
        return y + 12
    
    def _render_files(self, canvas: Canvas, y: int) -> int:
        """Render recent files list."""
        if not self._files:
            canvas.text(20, 60, "No loot files", colour='text_dim', font='medium')
            return y
        
        visible = self._files[self._scroll_offset:self._scroll_offset + self._visible_count]
        
        for i, f in enumerate(visible):
            actual_idx = self._scroll_offset + i
            is_selected = (actual_idx == self._selected)
            
            if is_selected:
                canvas.rect(0, y - 1, 124, y + 11, fill='bg_selected')
            
            # Category tag
            cat = f['category'][:4].upper()
            canvas.text(2, y, cat, colour='info', font='tiny')
            
            # Filename (truncated)
            name = f['name'][:12]
            text_colour = 'text' if is_selected else 'text_dim'
            canvas.text(25, y, name, colour=text_colour, font='tiny')
            
            # Size
            canvas.text(100, y, get_file_size_str(f['size']), colour='text_dim', font='tiny')
            
            y += 12
        
        # Scrollbar
        if len(self._files) > self._visible_count:
            bar_x = 125
            bar_y = 18
            bar_height = 72
            
            canvas.rect(bar_x, bar_y, 127, bar_y + bar_height, fill='scrollbar_bg')
            
            thumb_height = max(8, int(bar_height * self._visible_count / len(self._files)))
            max_offset = len(self._files) - self._visible_count
            thumb_pos = bar_y + int((bar_height - thumb_height) * self._scroll_offset / max_offset) if max_offset > 0 else bar_y
            
            canvas.rect(bar_x, thumb_pos, 127, thumb_pos + thumb_height, fill='scrollbar_thumb')
        
        return y
