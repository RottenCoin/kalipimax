#!/usr/bin/env python3
"""
KaliPiMax Logging
Centralised logging with file and console output.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from config import BASE_DIR


class Logger:
    """
    Unified logging for KaliPiMax.
    
    Logs to both console and file with appropriate levels.
    """
    
    _instance: Optional['Logger'] = None
    _logger: Optional[logging.Logger] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_logger()
        return cls._instance
    
    def _init_logger(self):
        """Initialise the logger."""
        self._logger = logging.getLogger('kalipimax')
        self._logger.setLevel(logging.DEBUG)
        
        # Prevent duplicate handlers
        if self._logger.handlers:
            return
        
        # Console handler (INFO and above)
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.INFO)
        console_fmt = logging.Formatter(
            '%(asctime)s │ %(levelname)-7s │ %(message)s',
            datefmt='%H:%M:%S'
        )
        console.setFormatter(console_fmt)
        self._logger.addHandler(console)
        
        # File handler (DEBUG and above)
        try:
            log_dir = BASE_DIR / 'logs'
            log_dir.mkdir(parents=True, exist_ok=True)
            
            log_file = log_dir / f"kalipimax_{datetime.now():%Y%m%d}.log"
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            file_fmt = logging.Formatter(
                '%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_fmt)
            self._logger.addHandler(file_handler)
        except Exception as e:
            self._logger.warning(f"Could not create log file: {e}")
    
    def debug(self, msg: str, *args, **kwargs):
        self._logger.debug(msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        self._logger.info(msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        self._logger.warning(msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        self._logger.error(msg, *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs):
        self._logger.critical(msg, *args, **kwargs)
    
    def exception(self, msg: str, *args, **kwargs):
        self._logger.exception(msg, *args, **kwargs)


# Global logger instance
log = Logger()
