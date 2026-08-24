"""Centralised logging setup.

Called once, at process start, from the composition root (`main.py`).
Keeping this separate from `config.py` avoids import-order surprises
(logging must be configured before any module-level `logger.info` calls
would otherwise fire silently into the default handler).
"""

from __future__ import annotations

import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger with a consistent, readable format.

    Args:
        level: Logging level name, e.g. "INFO" or "DEBUG".
    """
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    # httpx logs every request at INFO by default, which is noisy at our
    # own INFO level; demote it unless we're specifically debugging HTTP.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
