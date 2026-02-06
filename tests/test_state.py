#!/usr/bin/env python3
"""
KaliPiMax State Management Tests
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock hardware modules
from unittest.mock import MagicMock
sys.modules['RPi'] = MagicMock()
sys.modules['RPi.GPIO'] = MagicMock()
sys.modules['spidev'] = MagicMock()

import time
import pytest
from core.state import AppState, PayloadStatus, AlertLevel, Alert


class TestAppState:
    """Tests for AppState class."""
    
    def test_initial_state(self):
        """Test initial state values."""
        state = AppState()
        
        assert state.running is True
        assert state.backlight_on is True
        assert state.render_needed is True
        assert state.current_mode_index == 0
        assert state.payload_status == PayloadStatus.IDLE
        assert state.alerts == []
    
    def test_backlight_toggle(self):
        """Test backlight state toggling."""
        state = AppState()
        
        state.backlight_on = False
        assert state.backlight_on is False
        assert state.render_needed is True
        
        state.render_needed = False
        state.backlight_on = True
        assert state.backlight_on is True
        assert state.render_needed is True
    
    def test_add_alert(self):
        """Test adding alerts."""
        state = AppState()
        
        state.add_alert("Test message", AlertLevel.INFO)
        
        alerts = state.alerts
        assert len(alerts) == 1
        assert alerts[0].message == "Test message"
        assert alerts[0].level == AlertLevel.INFO
    
    def test_alert_limit(self):
        """Test that alerts are limited to max count."""
        state = AppState()
        
        # Add more than max alerts
        for i in range(60):
            state.add_alert(f"Alert {i}", AlertLevel.INFO)
        
        # Should be capped at ALERT_MAX_COUNT (50)
        assert len(state.alerts) == 50
    
    def test_clear_alerts(self):
        """Test clearing alerts."""
        state = AppState()
        
        state.add_alert("Test 1", AlertLevel.INFO)
        state.add_alert("Test 2", AlertLevel.INFO)
        
        assert len(state.alerts) == 2
        
        state.clear_alerts()
        
        assert len(state.alerts) == 0
    
    def test_payload_status(self):
        """Test payload status management."""
        state = AppState()
        
        assert state.is_payload_running() is False
        
        state.start_payload("Test", "echo hello")
        
        assert state.is_payload_running() is True
        assert state.payload_status == PayloadStatus.RUNNING
        assert state.current_payload.name == "Test"
        
        state.end_payload(PayloadStatus.SUCCESS)
        
        assert state.is_payload_running() is False
        assert state.payload_status == PayloadStatus.SUCCESS
    
    def test_confirmation_flow(self):
        """Test destructive action confirmation."""
        state = AppState()
        
        # First press - should return False (not confirmed)
        result = state.request_confirm("reboot", timeout=1.0)
        assert result is False
        
        # Second press within timeout - should return True (confirmed)
        result = state.request_confirm("reboot", timeout=1.0)
        assert result is True
        
        # Third press - timeout expired, should need new confirmation
        time.sleep(0.1)
        result = state.request_confirm("reboot", timeout=0.05)
        assert result is False
    
    def test_mode_change(self):
        """Test mode navigation."""
        state = AppState()
        
        # Mock modes
        class MockMode:
            def __init__(self, name):
                self.name = name
                self.entered = False
                self.exited = False
            
            def on_enter(self):
                self.entered = True
            
            def on_exit(self):
                self.exited = True
        
        modes = [MockMode("Mode1"), MockMode("Mode2"), MockMode("Mode3")]
        state.modes = modes
        
        # Should be at mode 0
        assert state.current_mode_index == 0
        
        # Move forward
        state.change_mode(1)
        assert state.current_mode_index == 1
        assert modes[0].exited is True
        assert modes[1].entered is True
        
        # Move backward
        state.change_mode(-1)
        assert state.current_mode_index == 0
        
        # Wrap around forward
        state.change_mode(3)
        assert state.current_mode_index == 0  # 0 + 3 % 3 = 0
    
    def test_activity_tracking(self):
        """Test last activity timestamp."""
        state = AppState()
        
        before = state.last_activity
        time.sleep(0.01)
        state.reset_activity()
        after = state.last_activity
        
        assert after > before


class TestAlert:
    """Tests for Alert dataclass."""
    
    def test_alert_creation(self):
        """Test alert creation."""
        alert = Alert(
            timestamp=1234567890.0,
            message="Test alert",
            level=AlertLevel.WARNING
        )
        
        assert alert.message == "Test alert"
        assert alert.level == AlertLevel.WARNING
    
    def test_alert_time_str(self):
        """Test alert time formatting."""
        # Use a known timestamp
        alert = Alert(
            timestamp=1234567890.0,
            message="Test",
            level=AlertLevel.INFO
        )
        
        # Should be HH:MM:SS format
        time_str = alert.time_str
        assert len(time_str) == 8
        assert time_str.count(':') == 2


class TestPayloadStatus:
    """Tests for PayloadStatus enum."""
    
    def test_status_values(self):
        """Test all status values exist."""
        assert PayloadStatus.IDLE
        assert PayloadStatus.RUNNING
        assert PayloadStatus.SUCCESS
        assert PayloadStatus.FAILED
        assert PayloadStatus.TIMEOUT
        assert PayloadStatus.CANCELLED


class TestAlertLevel:
    """Tests for AlertLevel enum."""
    
    def test_level_values(self):
        """Test all level values."""
        assert AlertLevel.INFO.value == "info"
        assert AlertLevel.OK.value == "ok"
        assert AlertLevel.WARNING.value == "warning"
        assert AlertLevel.ERROR.value == "error"
        assert AlertLevel.CRITICAL.value == "critical"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
