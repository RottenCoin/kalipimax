#!/usr/bin/env python3
"""
KaliPiMax State Management
Global application state with thread-safe access.
"""

import time
import threading
from collections import deque
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from enum import Enum, auto

from config import ALERT_MAX_COUNT


class PayloadStatus(Enum):
    """Payload execution states."""
    IDLE = auto()
    RUNNING = auto()
    SUCCESS = auto()
    FAILED = auto()
    TIMEOUT = auto()
    CANCELLED = auto()


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Single alert entry."""
    timestamp: float
    message: str
    level: AlertLevel = AlertLevel.INFO
    
    @property
    def time_str(self) -> str:
        return datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S")


@dataclass
class PayloadInfo:
    """Information about running payload."""
    name: str
    command: str
    start_time: float
    pid: Optional[int] = None
    
    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time


class AppState:
    """
    Thread-safe global application state.
    
    All state modifications should go through this class to ensure
    proper synchronisation and render triggering.
    """
    
    def __init__(self):
        self._lock = threading.RLock()
        
        # Application lifecycle
        self._running = True
        
        # Display state
        self._backlight_on = True
        self._render_needed = True
        self._last_activity = time.time()
        
        # Mode navigation
        self._current_mode_index = 0
        self._modes = []  # Set by main.py after mode registration
        
        # Payload execution
        self._payload_status = PayloadStatus.IDLE
        self._current_payload: Optional[PayloadInfo] = None
        
        # Alerts
        self._alerts: deque = deque(maxlen=ALERT_MAX_COUNT)
        
        # LCD reference (set during init)
        self._lcd = None
        
        # Confirmation state for destructive actions
        self._pending_confirm: Optional[str] = None
        self._confirm_expires: float = 0
    
    # -------------------------------------------------------------------------
    # Properties with thread-safe access
    # -------------------------------------------------------------------------
    
    @property
    def running(self) -> bool:
        with self._lock:
            return self._running
    
    @running.setter
    def running(self, value: bool):
        with self._lock:
            self._running = value
    
    @property
    def backlight_on(self) -> bool:
        with self._lock:
            return self._backlight_on
    
    @backlight_on.setter
    def backlight_on(self, value: bool):
        with self._lock:
            self._backlight_on = value
            self._render_needed = True
    
    @property
    def render_needed(self) -> bool:
        with self._lock:
            return self._render_needed
    
    @render_needed.setter
    def render_needed(self, value: bool):
        with self._lock:
            self._render_needed = value
    
    @property
    def last_activity(self) -> float:
        with self._lock:
            return self._last_activity
    
    @property
    def current_mode_index(self) -> int:
        with self._lock:
            return self._current_mode_index
    
    @property
    def payload_status(self) -> PayloadStatus:
        with self._lock:
            return self._payload_status
    
    @payload_status.setter
    def payload_status(self, value: PayloadStatus):
        with self._lock:
            self._payload_status = value
            self._render_needed = True
    
    @property
    def current_payload(self) -> Optional[PayloadInfo]:
        with self._lock:
            return self._current_payload
    
    @property
    def alerts(self) -> list:
        with self._lock:
            return list(self._alerts)
    
    @property
    def lcd(self):
        return self._lcd
    
    @lcd.setter
    def lcd(self, value):
        self._lcd = value
    
    @property
    def modes(self) -> list:
        with self._lock:
            return self._modes
    
    @modes.setter
    def modes(self, value: list):
        with self._lock:
            self._modes = value
    
    # -------------------------------------------------------------------------
    # Methods
    # -------------------------------------------------------------------------
    
    def reset_activity(self):
        """Record user activity (for backlight timeout)."""
        with self._lock:
            self._last_activity = time.time()
    
    def get_current_mode(self):
        """Get the currently active mode instance."""
        with self._lock:
            if self._modes and 0 <= self._current_mode_index < len(self._modes):
                return self._modes[self._current_mode_index]
            return None
    
    def change_mode(self, delta: int):
        """
        Change to a different mode.
        
        Args:
            delta: +1 for next, -1 for previous
        """
        # Resolve old/new modes under lock, but call lifecycle hooks
        # outside the lock — on_enter()/on_exit() may run subprocess
        # commands and must not block other threads.
        with self._lock:
            if not self._modes:
                return
            
            old_mode = self._modes[self._current_mode_index] if 0 <= self._current_mode_index < len(self._modes) else None
            self._current_mode_index = (self._current_mode_index + delta) % len(self._modes)
            new_mode = self._modes[self._current_mode_index] if 0 <= self._current_mode_index < len(self._modes) else None
            
            self._render_needed = True
            self._last_activity = time.time()
        
        if old_mode:
            old_mode.on_exit()
        if new_mode:
            new_mode.on_enter()
    
    def set_mode_by_name(self, name: str) -> bool:
        """Switch to a mode by its name."""
        old_mode = None
        new_mode = None
        found = False
        
        with self._lock:
            for i, mode in enumerate(self._modes):
                if mode.name.upper() == name.upper():
                    found = True
                    if self._current_mode_index != i:
                        old_mode = self._modes[self._current_mode_index] if 0 <= self._current_mode_index < len(self._modes) else None
                        self._current_mode_index = i
                        new_mode = self._modes[i]
                        self._render_needed = True
                    break
        
        if old_mode:
            old_mode.on_exit()
        if new_mode:
            new_mode.on_enter()
        
        return found
    
    def add_alert(self, message: str, level: AlertLevel = AlertLevel.INFO):
        """Add a new alert."""
        with self._lock:
            alert = Alert(
                timestamp=time.time(),
                message=message,
                level=level
            )
            self._alerts.append(alert)
            self._render_needed = True
            
            # Also print to console for debugging
            print(f"[{level.value.upper()}] {message}")
    
    def clear_alerts(self):
        """Clear all alerts."""
        with self._lock:
            self._alerts.clear()
            self._render_needed = True
    
    def start_payload(self, name: str, command: str, pid: Optional[int] = None):
        """Record that a payload has started."""
        with self._lock:
            self._current_payload = PayloadInfo(
                name=name,
                command=command,
                start_time=time.time(),
                pid=pid
            )
            self._payload_status = PayloadStatus.RUNNING
            self._render_needed = True
    
    def end_payload(self, status: PayloadStatus):
        """Record that a payload has finished."""
        with self._lock:
            self._current_payload = None
            self._payload_status = status
            self._render_needed = True
    
    def is_payload_running(self) -> bool:
        """Check if a payload is currently running."""
        with self._lock:
            return self._payload_status == PayloadStatus.RUNNING
    
    def request_confirm(self, action_name: str, timeout: float = 3.0) -> bool:
        """
        Request confirmation for a destructive action.
        
        Returns True if already confirmed (second press), False if first press.
        """
        with self._lock:
            now = time.time()
            
            if (self._pending_confirm == action_name and 
                now < self._confirm_expires):
                # Already confirmed
                self._pending_confirm = None
                return True
            
            # First press - set up confirmation
            self._pending_confirm = action_name
            self._confirm_expires = now + timeout
            return False
    
    def cancel_confirm(self):
        """Cancel pending confirmation."""
        with self._lock:
            self._pending_confirm = None


# Global singleton instance
state = AppState()
