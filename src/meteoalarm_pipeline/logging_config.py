"""Centralised logging setup.

Called once, at process start, from the composition root (`main.py`).
Keeping this separate from `config.py` avoids import-order surprises
(logging must be configured before any module-level `logger.info` calls
would otherwise fire silently into the default handler).
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger with a consistent, readable format.

    Args:
        level: Logging level name, e.g. "INFO" or "DEBUG".
    """
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Set up format
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level.upper())
    console_formatter = logging.Formatter(log_format, datefmt=date_format)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler with daily rotation
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=logs_dir / "meteoalarm.log",
        when="midnight",
        interval=1,
        backupCount=30,  # Keep 30 days of logs
        encoding="utf-8",
    )
    file_handler.setLevel(level.upper())
    file_formatter = logging.Formatter(log_format, datefmt=date_format)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Suppress noisy third-party loggers
    # httpx logs every request at INFO by default, which is noisy at our
    # own INFO level; demote it unless we're specifically debugging HTTP.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
