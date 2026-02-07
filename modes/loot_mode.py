#!/usr/bin/env python3
"""
KaliPiMax Loot Mode
Browse and manage captured data files.

Navigation:
    Enter mode → Files list
    ●/K1: Open selected file content
    ●/K1: Back to files (from content view)
    ←: Back one level (content→files→stats, or change mode)
    →: Forward one level (stats→files→content, or change mode)
    ↑↓: Navigate / scroll content
    K3: Cleanup files older than 7 days
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
    VIEW_CONTENT = 2
    
    _CONTENT_MAX_BYTES = 4096
    _CONTENT_LINE_WIDTH = 24
    _CONTENT_VISIBLE = 11
    
    def __init__(self):
        super().__init__("LOOT", "📁")
        
        self._view = self.VIEW_FILES
        self._stats = {}
        self._files = []
        self._selected = 0
        self._scroll_offset = 0
        self._visible_count = 6
        self._last_refresh = 0
        self._content_lines = []
        self._content_scroll = 0
        self._content_name = ""
    
    def on_enter(self):
        self._view = self.VIEW_FILES
        self._selected = 0
        self._scroll_offset = 0
        self._refresh_data()
    
    def _refresh_data(self):
        """Refresh loot statistics and file list."""
        self._stats = get_loot_stats()
        self._files = get_recent_files(20)
        self._last_refresh = time.time()
        
        # Adjust selection bounds
        max_items = len(LOOT_SUBDIRS) if self._view == self.VIEW_STATS else len(self._files)
        self._selected = min(self._selected, max(0, max_items - 1))
    
    # -----------------------------------------------------------------
    # Navigation
    # -----------------------------------------------------------------
    
    def on_up(self):
        if self._view == self.VIEW_CONTENT:
            if self._content_scroll > 0:
                self._content_scroll -= 1
                state.render_needed = True
            return
        if self._selected > 0:
            self._selected -= 1
            self._update_scroll()
            state.render_needed = True
    
    def on_down(self):
        if self._view == self.VIEW_CONTENT:
            max_scroll = max(0, len(self._content_lines) - self._CONTENT_VISIBLE)
            if self._content_scroll < max_scroll:
                self._content_scroll += 1
                state.render_needed = True
            return
        max_items = len(LOOT_SUBDIRS) if self._view == self.VIEW_STATS else len(self._files)
        if self._selected < max_items - 1:
            self._selected += 1
            self._update_scroll()
            state.render_needed = True
    
    def on_left(self):
        """Left: back one level, or change mode from top level."""
        if self._view == self.VIEW_CONTENT:
            self._view = self.VIEW_FILES
            state.render_needed = True
        elif self._view == self.VIEW_FILES:
            self._view = self.VIEW_STATS
            self._selected = 0
            self._scroll_offset = 0
            state.render_needed = True
        else:
            state.change_mode(-1)
    
    def on_right(self):
        """Right: forward one level, or change mode from deepest level."""
        if self._view == self.VIEW_STATS:
            self._view = self.VIEW_FILES
            self._selected = 0
            self._scroll_offset = 0
            state.render_needed = True
        elif self._view == self.VIEW_FILES:
            self._open_content()
        else:
            state.change_mode(1)
    
    def on_press(self):
        """Joystick press: open from any list, back from content."""
        if self._view == self.VIEW_CONTENT:
            self._view = self.VIEW_FILES
            state.render_needed = True
        elif self._view == self.VIEW_FILES:
            self._open_content()
        elif self._view == self.VIEW_STATS:
            self._view = self.VIEW_FILES
            self._selected = 0
            self._scroll_offset = 0
            state.render_needed = True
    
    def on_key1(self):
        """K1: same as joystick press."""
        self.on_press()
    
    def on_key3(self):
        """Cleanup old files."""
        deleted = delete_old_files(7)
        state.add_alert(f"Deleted {deleted} files (>7d)", AlertLevel.OK)
        self._refresh_data()
        state.render_needed = True
    
    def _update_scroll(self):
        if self._selected < self._scroll_offset:
            self._scroll_offset = self._selected
        elif self._selected >= self._scroll_offset + self._visible_count:
            self._scroll_offset = self._selected - self._visible_count + 1
    
    # -----------------------------------------------------------------
    # Content viewer
    # -----------------------------------------------------------------
    
    def _open_content(self):
        """Load and display selected file's content."""
        if not self._files:
            state.add_alert("No loot files found", AlertLevel.WARNING)
            state.render_needed = True
            return
        if self._selected >= len(self._files):
            state.add_alert("Selection out of range", AlertLevel.ERROR)
            state.render_needed = True
            return
        try:
            f = self._files[self._selected]
            self._content_name = f['name']
            self._content_lines = self._load_content(f['path'])
            self._content_scroll = 0
            self._view = self.VIEW_CONTENT
            state.render_needed = True
        except Exception as e:
            state.add_alert(f"Open: {str(e)[:25]}", AlertLevel.ERROR)
            state.render_needed = True
    
    def _load_content(self, filepath) -> list:
        """Read file and return wrapped lines for display."""
        try:
            with open(filepath, 'rb') as fh:
                raw = fh.read(self._CONTENT_MAX_BYTES)
        except Exception as e:
            return [f"[Error: {str(e)[:20]}]"]
        
        # Detect binary (null bytes in first 512 bytes)
        if b'\x00' in raw[:512]:
            return [
                "[Binary file]",
                f"{len(raw)} bytes read",
                "",
                "Use CLI/SCP to",
                "transfer & view",
            ]
        
        try:
            text = raw.decode('utf-8', errors='replace')
        except Exception:
            return ["[Decode error]"]
        
        w = self._CONTENT_LINE_WIDTH
        lines = []
        for line in text.splitlines():
            line = line.rstrip()
            if not line:
                lines.append("")
                continue
            while len(line) > w:
                lines.append(line[:w])
                line = line[w:]
            lines.append(line)
        
        if not lines:
            lines = ["[Empty file]"]
        
        return lines
    
    # -----------------------------------------------------------------
    # Rendering
    # -----------------------------------------------------------------
    
    def render(self) -> Image.Image:
        canvas = self._create_canvas()
        
        # Auto-refresh every 10s (not in content view)
        if self._view != self.VIEW_CONTENT and time.time() - self._last_refresh > 10:
            self._refresh_data()
        
        y = 2
        
        # Header
        if self._view == self.VIEW_CONTENT:
            name = self._content_name[:14]
            canvas.text(2, y, name, colour='title', font='title')
        else:
            view_name = "Stats" if self._view == self.VIEW_STATS else "Files"
            canvas.text(2, y, f"LOOT [{view_name}]", colour='title', font='title')
        y += 16
        
        if self._view == self.VIEW_STATS:
            y = self._render_stats(canvas, y)
            canvas.footer("●:Files  K3:Cleanup")
        elif self._view == self.VIEW_FILES:
            y = self._render_files(canvas, y)
            canvas.footer("●:Open  K3:Cleanup")
        else:
            self._render_content(canvas, y)
            canvas.footer("●:Back  \u2191\u2193:Scroll")
        
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
    
    def _render_content(self, canvas: Canvas, y: int) -> int:
        """Render scrollable file content."""
        visible = self._content_lines[
            self._content_scroll:self._content_scroll + self._CONTENT_VISIBLE
        ]
        
        for line in visible:
            canvas.text(2, y, line[:self._CONTENT_LINE_WIDTH], colour='text', font='tiny')
            y += 9
        
        # Scroll position indicator
        total = len(self._content_lines)
        if total > self._CONTENT_VISIBLE:
            pos = self._content_scroll + 1
            end = min(self._content_scroll + self._CONTENT_VISIBLE, total)
            canvas.text(85, 2, f"{pos}-{end}/{total}", colour='text_dim', font='tiny')
        
        return y
