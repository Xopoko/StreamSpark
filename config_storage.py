#!/usr/bin/env python3
"""
Minimal deprecated config storage shim.

This file provides a no-op API-compatible shim. Methods deliberately accept
*args/**kwargs so parameters that are unused do not trigger static analysis
warnings and the API remains compatible with legacy callers.
"""

import logging
from typing import Any, Dict, Optional


class ConfigStorage:
    """Deprecated no-op config storage (minimal shim)."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.warning("config_storage is deprecated and acting as a no-op shim.")
        self._app: Dict[str, Any] = {}

    # App-level config
    def get_app_config(self, key: str, default=None, *args, **kwargs):
        return self._app.get(key, default)

    def set_app_config(self, key: str, value, *args, **kwargs) -> bool:
        self._app[key] = value
        return True

    # OAuth tokens (legacy API)
    def set_user_oauth_token(self, *args, **kwargs) -> bool:
        return True

    def get_user_oauth_token(self, *args, **kwargs):
        return None

    # User config (legacy API)
    def ensure_user_exists(self, *args, **kwargs) -> bool:
        return True

    def init_user_config(self, *args, **kwargs) -> None:
        return None

    def get_config(self, *args, **kwargs):
        return None

    def set_config(self, *args, **kwargs) -> bool:
        return True

    def get_all_config(self, *args, **kwargs):
        return {}

    def delete_config(self, *args, **kwargs) -> bool:
        return True

    # Users (legacy API)
    def create_user(self, *args, **kwargs):
        return None

    def get_user_by_email(self, *args, **kwargs):
        return None

    def get_user_by_id(self, *args, **kwargs):
        return None

    # Exchange rates cache (no-op shim)
    def get_exchange_rate(self, *args, **kwargs):
        return None

    def set_exchange_rate(self, *args, **kwargs) -> bool:
        return True


# Global instance for legacy imports
config_storage = ConfigStorage()
