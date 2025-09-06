#!/usr/bin/env python3
"""
Logging utilities for the StreamSpark FastAPI application.
Provides in-memory log storage for real-time viewing and unified logging setup.
"""

import os
import sys
import logging
from collections import deque
from typing import Deque, Dict, Any, List

# Global log storage for real-time console
log_memory: Deque[Dict[str, Any]] = deque(maxlen=500)  # Keep last 500 log entries


class MemoryLogHandler(logging.Handler):
    """Custom logging handler that stores logs in memory for real-time viewing."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            log_entry = {
                "timestamp": int(record.created * 1000),  # milliseconds
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            log_memory.append(log_entry)
        except Exception:
            # Avoid raising from logging
            pass


def setup_logging() -> None:
    """Setup application logging with both file, console and memory output."""
    os.makedirs("logs", exist_ok=True)

    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    level = logging.INFO

    memory_handler = MemoryLogHandler()

    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=[
            logging.FileHandler("logs/donation_app.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
            memory_handler,
        ],
    )

    # Attach memory handler to common ASGI server loggers (uvicorn/gunicorn)
    for logger_name in [
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "gunicorn",
        "gunicorn.error",
        "gunicorn.access",
        "fastapi",
        "starlette",
    ]:
        try:
            logger = logging.getLogger(logger_name)
            logger.setLevel(level)
            logger.addHandler(memory_handler)
            # Avoid duplicate logs if root already handles
            logger.propagate = True
        except Exception:
            pass


def get_recent_logs(since_ms: int = 0) -> List[Dict[str, Any]]:
    """Return logs newer than the provided timestamp in ms."""
    return [entry for entry in list(log_memory) if entry["timestamp"] > since_ms]
