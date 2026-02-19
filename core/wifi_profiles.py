#!/usr/bin/env python3
"""
KaliPiMax WiFi Profile Storage
Stores known WiFi network credentials in wifi_profiles.json.
"""

import json
from pathlib import Path

from config import BASE_DIR

_PROFILES_FILE = BASE_DIR / "wifi_profiles.json"


def load_profiles() -> dict:
    """Load all stored profiles. Returns {ssid: password}."""
    try:
        if _PROFILES_FILE.exists():
            return json.loads(_PROFILES_FILE.read_text())
    except Exception:
        pass
    return {}


def save_profiles(profiles: dict):
    """Save all profiles to disk."""
    try:
        _PROFILES_FILE.write_text(json.dumps(profiles, indent=2))
    except Exception:
        pass


def get_password(ssid: str) -> str:
    """Get stored password for an SSID. Returns None if not found."""
    return load_profiles().get(ssid)


def store_password(ssid: str, password: str):
    """Store or update a password for an SSID."""
    profiles = load_profiles()
    profiles[ssid] = password
    save_profiles(profiles)


def forget_network(ssid: str):
    """Remove a stored network."""
    profiles = load_profiles()
    if ssid in profiles:
        del profiles[ssid]
        save_profiles(profiles)


def is_known(ssid: str) -> bool:
    """Check if an SSID has a stored password."""
    return ssid in load_profiles()
