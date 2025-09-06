#!/usr/bin/env python3
"""
Global application state for FastAPI dependency injection.
Holds the initialized AppContainer for access within routers.
"""

from typing import Optional
from .container import AppContainer

_container: Optional[AppContainer] = None


def set_container(c: AppContainer) -> None:
    """Set the global application container (called during app startup)."""
    global _container
    _container = c


def get_container() -> AppContainer:
    """Get the global application container."""
    assert _container is not None, "App container not initialized"
    return _container
