#!/usr/bin/env python3
"""
KaliPiMax Test Configuration
Fixtures and helpers for unit tests.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Mock RPi.GPIO and spidev before importing anything else
sys.modules['RPi'] = MagicMock()
sys.modules['RPi.GPIO'] = MagicMock()
sys.modules['spidev'] = MagicMock()


import pytest
from PIL import Image


@pytest.fixture
def mock_gpio():
    """Mock GPIO module."""
    with patch.dict('sys.modules', {
        'RPi': MagicMock(),
        'RPi.GPIO': MagicMock(),
        'spidev': MagicMock(),
    }):
        yield


@pytest.fixture
def app_state():
    """Fresh AppState instance for testing."""
    from core.state import AppState
    state = AppState()
    return state


@pytest.fixture
def canvas():
    """Canvas instance for rendering tests."""
    from ui.renderer import Canvas
    return Canvas()


@pytest.fixture
def sample_menu_items():
    """Sample menu items for menu testing."""
    return [
        {'icon': '●', 'text': 'Item 1', 'action': lambda: None},
        {'icon': '●', 'text': 'Item 2', 'action': lambda: None},
        {'icon': '●', 'text': 'Item 3', 'action': lambda: None},
        {'icon': '●', 'text': 'Item 4', 'action': lambda: None},
        {'icon': '●', 'text': 'Item 5', 'action': lambda: None},
        {'icon': '●', 'text': 'Item 6', 'action': lambda: None},
        {'icon': '●', 'text': 'Item 7', 'action': lambda: None},
        {'icon': '●', 'text': 'Item 8', 'action': lambda: None},
        {'icon': '●', 'text': 'Item 9', 'action': lambda: None},
        {'icon': '●', 'text': 'Item 10', 'action': lambda: None},
    ]
