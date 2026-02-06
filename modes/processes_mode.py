#!/usr/bin/env python3
"""
KaliPiMax Processes Mode
View and manage running processes with kill functionality.
"""

import subprocess
import time
import psutil
from PIL import Image

from ui.base_mode import BaseMode
from ui.renderer import Canvas, MenuRenderer
from core.state import state, AlertLevel
from config import PROCESS_LIST_COUNT, MENU_VISIBLE_ITEMS


class ProcessesMode(BaseMode):
    """
    Process management mode.
    
    Shows top processes by CPU usage with ability to kill them.
    PRESS: SIGTERM (graceful), KEY3: SIGKILL (force)
    """
    
    def __init__(self):
        super().__init__("PROCESSES", "📊")
        
        self._processes = []
        self._selected = 0
        self._scroll_offset = 0
        self._last_refresh = 0
        self._refresh_interval = 2.0
        self._visible_count = 6  # Fewer items due to header
    
    def on_enter(self):
        """Refresh process list when entering mode."""
        self._refresh_processes()
        self._selected = 0
        self._scroll_offset = 0
    
    def _refresh_processes(self):
        """Get top processes by CPU usage."""
        procs = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                info = proc.info
                # Only include processes using resources
                if info['cpu_percent'] > 0 or info['memory_percent'] > 1:
                    procs.append({
                        'pid': info['pid'],
                        'name': info['name'][:10],
                        'cpu': info['cpu_percent'],
                        'mem': info['memory_percent'],
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Sort by CPU usage descending
        procs.sort(key=lambda x: x['cpu'], reverse=True)
        self._processes = procs[:PROCESS_LIST_COUNT]
        self._last_refresh = time.time()
        
        # Adjust selection if needed
        if self._selected >= len(self._processes):
            self._selected = max(0, len(self._processes) - 1)
    
    def _kill_process(self, signal: int = 15):
        """Kill the selected process."""
        if not self._processes or self._selected >= len(self._processes):
            return
        
        proc = self._processes[self._selected]
        pid = proc['pid']
        name = proc['name']
        
        try:
            sig_name = "SIGTERM" if signal == 15 else "SIGKILL"
            subprocess.run(
                ['sudo', 'kill', f'-{signal}', str(pid)],
                timeout=2,
                capture_output=True
            )
            state.add_alert(f"Killed {name} ({pid}) [{sig_name}]", AlertLevel.OK)
            
            # Wait briefly and refresh
            time.sleep(0.3)
            self._refresh_processes()
            state.render_needed = True
            
        except Exception as e:
            state.add_alert(f"Kill failed: {e}", AlertLevel.ERROR)
    
    def on_up(self):
        """Move selection up."""
        if self._selected > 0:
            self._selected -= 1
            self._update_scroll()
            state.render_needed = True
    
    def on_down(self):
        """Move selection down."""
        if self._selected < len(self._processes) - 1:
            self._selected += 1
            self._update_scroll()
            state.render_needed = True
    
    def _update_scroll(self):
        """Update scroll offset to keep selection visible."""
        if self._selected < self._scroll_offset:
            self._scroll_offset = self._selected
        elif self._selected >= self._scroll_offset + self._visible_count:
            self._scroll_offset = self._selected - self._visible_count + 1
    
    def on_press(self):
        """Kill selected process with SIGTERM (graceful)."""
        self._kill_process(15)
    
    def on_key3(self):
        """Force kill selected process with SIGKILL."""
        self._kill_process(9)
    
    def render(self) -> Image.Image:
        canvas = self._create_canvas()
        
        # Auto-refresh
        if time.time() - self._last_refresh > self._refresh_interval:
            # Try to keep same PID selected after refresh
            old_pid = None
            if self._processes and self._selected < len(self._processes):
                old_pid = self._processes[self._selected]['pid']
            
            self._refresh_processes()
            
            # Find old PID in new list
            if old_pid:
                for i, proc in enumerate(self._processes):
                    if proc['pid'] == old_pid:
                        self._selected = i
                        self._update_scroll()
                        break
        
        y = self._render_header(canvas)
        
        # Column headers
        canvas.text(2, y, "PID  NAME       CPU% MEM%", colour='text_dim', font='tiny')
        y += 10
        
        # Process list
        visible_procs = self._processes[self._scroll_offset:self._scroll_offset + self._visible_count]
        
        for i, proc in enumerate(visible_procs):
            actual_idx = self._scroll_offset + i
            is_selected = (actual_idx == self._selected)
            
            # Selection highlight
            if is_selected:
                canvas.rect(0, y - 1, 124, y + 10, fill='bg_selected')
            
            # Colour based on CPU usage
            if proc['cpu'] > 50:
                text_colour = 'error'
            elif proc['cpu'] > 20:
                text_colour = 'warning'
            elif is_selected:
                text_colour = 'highlight'
            else:
                text_colour = 'text_dim'
            
            # Format line
            pid = str(proc['pid'])[:5].rjust(5)
            name = proc['name'][:10].ljust(10)
            cpu = f"{proc['cpu']:.0f}".rjust(3)
            mem = f"{proc['mem']:.0f}".rjust(3)
            
            line = f"{pid} {name} {cpu}% {mem}%"
            canvas.text(2, y, line, colour=text_colour, font='tiny')
            y += 11
        
        # Scrollbar
        if len(self._processes) > self._visible_count:
            self._draw_scrollbar(canvas)
        
        # Footer
        total = len(self._processes)
        canvas.text(2, 108, f"{self._selected + 1}/{total}", colour='text_dim', font='tiny')
        canvas.footer("●:Kill K3:Force kill")
        
        return canvas.get_image()
    
    def _draw_scrollbar(self, canvas: Canvas):
        """Draw scroll indicator."""
        bar_x = 125
        bar_y = 28
        bar_height = 66
        
        # Background
        canvas.rect(bar_x, bar_y, 127, bar_y + bar_height, fill='scrollbar_bg')
        
        # Thumb
        total = len(self._processes)
        thumb_height = max(8, int(bar_height * self._visible_count / total))
        thumb_pos = bar_y + int(
            (bar_height - thumb_height) * self._scroll_offset / (total - self._visible_count)
        ) if total > self._visible_count else bar_y
        
        canvas.rect(bar_x, thumb_pos, 127, thumb_pos + thumb_height, fill='scrollbar_thumb')
