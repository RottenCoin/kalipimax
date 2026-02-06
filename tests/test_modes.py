#!/usr/bin/env python3
"""
KaliPiMax Mode Tests
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock hardware modules
from unittest.mock import MagicMock, patch
sys.modules['RPi'] = MagicMock()
sys.modules['RPi.GPIO'] = MagicMock()
sys.modules['spidev'] = MagicMock()

import pytest
from PIL import Image

from config import DISPLAY_WIDTH, DISPLAY_HEIGHT
from ui.base_mode import BaseMode, MenuMode, InfoMode
from core.state import state, AlertLevel


class ConcreteMode(BaseMode):
    """Concrete implementation for testing abstract base."""
    
    def render(self):
        canvas = self._create_canvas()
        canvas.header(self.name)
        return canvas.get_image()


class TestBaseMode:
    """Tests for BaseMode class."""
    
    def test_mode_creation(self):
        """Test mode creation."""
        mode = ConcreteMode("TEST", "●")
        
        assert mode.name == "TEST"
        assert mode.icon == "●"
    
    def test_mode_render_returns_image(self):
        """Test render returns PIL Image."""
        mode = ConcreteMode("TEST", "●")
        
        img = mode.render()
        
        assert isinstance(img, Image.Image)
        assert img.size == (DISPLAY_WIDTH, DISPLAY_HEIGHT)
    
    def test_mode_lifecycle(self):
        """Test on_enter and on_exit are callable."""
        mode = ConcreteMode("TEST", "●")
        
        # Should not raise
        mode.on_enter()
        mode.on_exit()
    
    def test_mode_default_key_handlers(self):
        """Test default key handlers don't crash."""
        mode = ConcreteMode("TEST", "●")
        
        # These should not raise
        mode.on_key1()
        mode.on_key3()
        mode.on_up()
        mode.on_down()
        mode.on_press()


class TestMenuMode:
    """Tests for MenuMode class."""
    
    def test_menu_mode_items(self):
        """Test menu mode with items."""
        class TestMenuMode(MenuMode):
            def __init__(self):
                super().__init__("TEST")
                self._menu_items = [
                    {'text': 'Item 1', 'action': lambda: None},
                    {'text': 'Item 2', 'action': lambda: None},
                ]
        
        mode = TestMenuMode()
        mode.on_enter()
        
        assert mode._menu is not None
        assert len(mode._menu.items) == 2
    
    def test_menu_mode_navigation(self):
        """Test menu navigation."""
        class TestMenuMode(MenuMode):
            def __init__(self):
                super().__init__("TEST")
                self._menu_items = [
                    {'text': f'Item {i}', 'action': lambda: None}
                    for i in range(5)
                ]
        
        mode = TestMenuMode()
        mode.on_enter()
        
        assert mode._get_selected_index() == 0
        
        mode.on_down()
        assert mode._get_selected_index() == 1
        
        mode.on_up()
        assert mode._get_selected_index() == 0
    
    def test_menu_mode_render(self):
        """Test menu mode renders."""
        class TestMenuMode(MenuMode):
            def __init__(self):
                super().__init__("TEST")
                self._menu_items = [
                    {'text': 'Item 1', 'action': lambda: None},
                ]
        
        mode = TestMenuMode()
        mode.on_enter()
        
        img = mode.render()
        
        assert isinstance(img, Image.Image)
    
    def test_menu_mode_execute(self):
        """Test menu item execution."""
        executed = {'called': False}
        
        def action():
            executed['called'] = True
        
        class TestMenuMode(MenuMode):
            def __init__(self):
                super().__init__("TEST")
                self._menu_items = [
                    {'text': 'Item 1', 'action': action},
                ]
        
        mode = TestMenuMode()
        mode.on_enter()
        mode.on_press()
        
        assert executed['called'] is True


class TestInfoMode:
    """Tests for InfoMode class."""
    
    def test_info_mode_refresh(self):
        """Test info mode data refresh."""
        class TestInfoMode(InfoMode):
            def __init__(self):
                super().__init__("TEST")
                self.refresh_count = 0
            
            def _refresh_data(self):
                super()._refresh_data()
                self.refresh_count += 1
            
            def render(self):
                return self._create_canvas().get_image()
        
        mode = TestInfoMode()
        mode.on_enter()
        
        assert mode.refresh_count == 1
        
        # KEY3 should force refresh
        mode.on_key3()
        
        assert mode.refresh_count == 2


class TestSystemMode:
    """Tests for SystemMode."""
    
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    def test_system_mode_render(self, mock_mem, mock_cpu):
        """Test system mode renders system info."""
        from modes.system_mode import SystemMode
        
        mock_cpu.return_value = 45.0
        mock_mem.return_value = MagicMock(
            percent=60.0,
            used=512 * 1024 * 1024  # 512MB
        )
        
        mode = SystemMode()
        mode.on_enter()
        
        img = mode.render()
        
        assert isinstance(img, Image.Image)


class TestNmapMode:
    """Tests for NmapMode."""
    
    @patch('subprocess.run')
    def test_nmap_mode_network_detection(self, mock_run):
        """Test Nmap mode detects network."""
        from modes.nmap_mode import NmapMode, get_network_cidr
        
        mock_run.return_value = MagicMock(
            stdout="192.168.1.100/24\n",
            returncode=0
        )
        
        cidr = get_network_cidr()
        
        assert '192.168.1' in cidr
    
    def test_nmap_mode_render(self):
        """Test Nmap mode renders."""
        from modes.nmap_mode import NmapMode
        
        mode = NmapMode()
        mode.on_enter()
        
        img = mode.render()
        
        assert isinstance(img, Image.Image)


class TestAlertsMode:
    """Tests for AlertsMode."""
    
    def test_alerts_mode_render_empty(self):
        """Test alerts mode with no alerts."""
        from modes.alerts_mode import AlertsMode
        
        # Clear alerts
        state.clear_alerts()
        
        mode = AlertsMode()
        mode.on_enter()
        
        img = mode.render()
        
        assert isinstance(img, Image.Image)
    
    def test_alerts_mode_render_with_alerts(self):
        """Test alerts mode with alerts."""
        from modes.alerts_mode import AlertsMode
        
        # Add some alerts
        state.clear_alerts()
        state.add_alert("Test 1", AlertLevel.INFO)
        state.add_alert("Test 2", AlertLevel.WARNING)
        state.add_alert("Test 3", AlertLevel.ERROR)
        
        mode = AlertsMode()
        mode.on_enter()
        
        img = mode.render()
        
        assert isinstance(img, Image.Image)
    
    def test_alerts_mode_clear(self):
        """Test clearing alerts from mode."""
        from modes.alerts_mode import AlertsMode
        
        state.clear_alerts()
        state.add_alert("Test", AlertLevel.INFO)
        
        assert len(state.alerts) == 1
        
        mode = AlertsMode()
        mode.on_key3()
        
        assert len(state.alerts) == 0


class TestProcessesMode:
    """Tests for ProcessesMode."""
    
    @patch('psutil.process_iter')
    def test_processes_mode_render(self, mock_iter):
        """Test processes mode renders."""
        from modes.processes_mode import ProcessesMode
        
        # Mock process iterator
        mock_proc = MagicMock()
        mock_proc.info = {
            'pid': 1234,
            'name': 'test_proc',
            'cpu_percent': 10.0,
            'memory_percent': 5.0,
        }
        mock_iter.return_value = [mock_proc]
        
        mode = ProcessesMode()
        mode.on_enter()
        
        img = mode.render()
        
        assert isinstance(img, Image.Image)


class TestAllModesRender:
    """Test all modes can render without error."""
    
    def test_all_modes_render(self):
        """Every mode should render without crashing."""
        from modes import get_all_modes
        
        modes = get_all_modes()
        
        assert len(modes) > 0
        
        for mode in modes:
            mode.on_enter()
            
            try:
                img = mode.render()
                assert isinstance(img, Image.Image), f"{mode.name} did not return Image"
                assert img.size == (DISPLAY_WIDTH, DISPLAY_HEIGHT), f"{mode.name} wrong size"
            except Exception as e:
                pytest.fail(f"Mode {mode.name} failed to render: {e}")
            
            mode.on_exit()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
