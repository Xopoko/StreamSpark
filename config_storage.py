#!/usr/bin/env python3
"""
DEPRECATED: No database storage.

This module used to provide a SQLite-backed configuration store.
The application no longer uses any database. All configuration is kept in-memory
via the Config object (see config.py), and endpoints update runtime state directly.

This stub remains only to avoid import errors if any legacy code references it.
All methods are no-ops or return defaults.
"""

import logging
from typing import Optional, Dict, Any


class ConfigStorage:
    """Deprecated no-op config storage."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.warning("config_storage is deprecated and no longer used. All data is in-memory.")
        # Optional in-memory fallback to avoid breaking behavior where 'True' return is expected
        self._app: Dict[str, Any] = {}

    # App-level config
    def get_app_config(self, key: str, default=None):
        return self._app.get(key, default)

    def set_app_config(self, key: str, value, value_type: str = "string", description: Optional[str] = None) -> bool:
        self._app[key] = value
        return True

    # OAuth tokens (legacy API)
    def set_user_oauth_token(self, user_id, access_token, refresh_token=None, token_type="Bearer", expires_at=None) -> bool:
        return True

    def get_user_oauth_token(self, user_id):
        return None

    # User config (legacy API)
    def ensure_user_exists(self, user_id, email=None, name=None) -> bool:
        return True

    def init_user_config(self, user_id) -> None:
        return None

    def get_config(self, user_id, key, default=None):
        return default

    def set_config(self, user_id, key, value, value_type="string", description=None) -> bool:
        return True

    def get_all_config(self, user_id):
        return {}

    def delete_config(self, user_id, key) -> bool:
        return True

    # Users (legacy API)
    def create_user(self, email, password, first_name=None, last_name=None):
        return None

    def get_user_by_email(self, email):
        return None

    def get_user_by_id(self, user_id):
        return None

    # Exchange rates cache (now handled in-memory in CurrencyConverter)
    def get_exchange_rate(self, from_currency, to_currency):
        return None

    def set_exchange_rate(self, from_currency, to_currency, rate, cache_minutes=5, source=None) -> bool:
        return True


# Global instance for legacy imports
config_storage = ConfigStorage()
