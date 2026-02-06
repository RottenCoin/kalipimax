#!/usr/bin/env python3
"""
KaliPiMax Payload Execution
Background command execution with status tracking.
"""

import subprocess
import threading
import signal
import os
from typing import Optional, Callable
from datetime import datetime

from config import PAYLOAD_TIMEOUT, LOOT_DIR
from core.state import state, PayloadStatus, AlertLevel
from core.logger import log


class PayloadRunner:
    """
    Executes payloads (shell commands) in background threads.
    Provides status tracking, timeout handling, and cancellation.
    """
    
    def __init__(self):
        self._current_process: Optional[subprocess.Popen] = None
        self._cancel_requested = False
    
    def run(
        self,
        command: str,
        description: str,
        timeout: int = PAYLOAD_TIMEOUT,
        on_complete: Optional[Callable] = None
    ):
        """
        Run a payload command in a background thread.
        
        Args:
            command: Shell command to execute
            description: Human-readable description for display
            timeout: Maximum execution time in seconds
            on_complete: Optional callback when finished
        """
        if state.is_payload_running():
            state.add_alert("Payload already running", AlertLevel.WARNING)
            return
        
        self._cancel_requested = False
        
        def runner():
            state.start_payload(description, command)
            state.add_alert(f"Starting: {description}", AlertLevel.INFO)
            
            try:
                # Run the command
                self._current_process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    preexec_fn=os.setsid  # Create new process group for clean kill
                )
                
                try:
                    stdout, stderr = self._current_process.communicate(timeout=timeout)
                    
                    if self._cancel_requested:
                        state.add_alert(f"Cancelled: {description}", AlertLevel.WARNING)
                        state.end_payload(PayloadStatus.CANCELLED)
                    elif self._current_process.returncode == 0:
                        state.add_alert(f"✓ {description} complete", AlertLevel.OK)
                        state.end_payload(PayloadStatus.SUCCESS)
                    else:
                        error_msg = stderr.decode()[:50] if stderr else "Unknown error"
                        state.add_alert(f"✗ {description}: {error_msg}", AlertLevel.ERROR)
                        state.end_payload(PayloadStatus.FAILED)
                        
                except subprocess.TimeoutExpired:
                    self._kill_process()
                    state.add_alert(f"⏱ {description} timeout ({timeout}s)", AlertLevel.WARNING)
                    state.end_payload(PayloadStatus.TIMEOUT)
                    
            except Exception as e:
                state.add_alert(f"Error: {str(e)[:40]}", AlertLevel.ERROR)
                state.end_payload(PayloadStatus.FAILED)
            
            finally:
                self._current_process = None
                if on_complete:
                    on_complete()
        
        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
    
    def cancel(self):
        """Cancel the currently running payload."""
        if not state.is_payload_running():
            return
        
        self._cancel_requested = True
        self._kill_process()
    
    def _kill_process(self):
        """Kill the current process and all children."""
        if self._current_process:
            try:
                # Kill the entire process group
                os.killpg(os.getpgid(self._current_process.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                try:
                    self._current_process.kill()
                except:
                    pass
    
    def kill_all_tools(self):
        """Kill common offensive tools."""
        tools = [
            "nmap", "responder", "arpspoof", "dnsspoof", "sslstrip",
            "tcpdump", "airodump-ng", "aireplay-ng", "airmon-ng",
            "bettercap", "tshark", "msfconsole"
        ]
        
        for tool in tools:
            try:
                subprocess.run(
                    f"sudo pkill -9 {tool}",
                    shell=True,
                    timeout=2,
                    capture_output=True
                )
            except:
                pass
        
        state.add_alert("All tools killed", AlertLevel.OK)


def get_timestamp() -> str:
    """Get a timestamp string for filenames."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def get_loot_path(category: str, prefix: str, extension: str = "txt") -> str:
    """
    Generate a loot file path with timestamp.
    
    Args:
        category: Subdirectory (nmap, responder, mitm, etc.)
        prefix: Filename prefix
        extension: File extension
    
    Returns:
        Full path to loot file
    """
    loot_subdir = LOOT_DIR / category
    loot_subdir.mkdir(parents=True, exist_ok=True)
    return str(loot_subdir / f"{prefix}_{get_timestamp()}.{extension}")


# Singleton instance
payload_runner = PayloadRunner()
