"""DonationAlerts HTTP client.

Encapsulates API calls and token refresh logic separate from the polling loop.
"""

import logging
import time
from typing import Any, Dict, List, Optional

import requests


class DonationAlertsClient:
    def __init__(self, config, logger: Optional[logging.Logger] = None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.api_base = "https://www.donationalerts.com/api/v1"
        self.oauth_token_url = "https://www.donationalerts.com/oauth/token"
        self.api_token: Optional[str] = None

    def set_api_token(self, token: str) -> None:
        self.api_token = token

    def has_token(self) -> bool:
        return bool(self.api_token)

    def get_api_token(self) -> Optional[str]:
        return self.api_token

    def fetch_donations(self, page: int = 1, limit: int = 10) -> Optional[List[Dict[str, Any]]]:
        """Fetch donations. Handles 401 by refreshing token and retrying once."""
        if not self.api_token:
            return None

        try:
            url = f"{self.api_base}/alerts/donations"
            params = {"page": page, "limit": limit}
            headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Accept": "application/json",
            }

            response = requests.get(url, headers=headers, params=params, timeout=10)

            if response.status_code == 401:
                self.logger.warning("API authentication failed (401). Attempting to refresh access token...")
                if self.refresh_access_token():
                    headers["Authorization"] = f"Bearer {self.api_token}"
                    response = requests.get(url, headers=headers, params=params, timeout=10)
                    if response.status_code != 200:
                        self.logger.error(f"API request failed after refresh: {response.status_code} - {response.text}")
                        return None
                else:
                    self.logger.error(f"API authentication failed and refresh not possible. Response: {response.text}")
                    return None
            elif response.status_code == 429:
                self.logger.warning("API rate limit hit - backing off 10 seconds")
                time.sleep(10)
                return None
            elif response.status_code != 200:
                self.logger.error(f"API request failed: {response.status_code} - {response.text}")
                return None

            data = response.json() or {}
            donations = data.get("data", [])
            return donations

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error fetching donations: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error fetching donations: {e}")
            return None

    def refresh_access_token(self) -> bool:
        """Refresh OAuth access token using stored refresh token and update in-memory config."""
        try:
            client_id = getattr(self.config, "donationalerts_client_id", None)
            client_secret = getattr(self.config, "donationalerts_client_secret", None)
            refresh_token = getattr(self.config, "donationalerts_refresh_token", None)
            if not client_id or not client_secret or not refresh_token:
                self.logger.warning("Cannot refresh token: missing client credentials or refresh_token")
                return False

            data = {
                "grant_type": "refresh_token",
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
            }
            resp = requests.post(self.oauth_token_url, data=data, timeout=15)
            if resp.status_code != 200:
                self.logger.error(f"Token refresh failed: {resp.status_code} - {resp.text}")
                return False

            token = resp.json() or {}
            access_token = token.get("access_token")
            new_refresh_token = token.get("refresh_token") or refresh_token
            expires_in = token.get("expires_in")

            if not access_token:
                self.logger.error("Token refresh response missing access_token")
                return False

            # Update in-memory token and config
            self.set_api_token(access_token)
            setattr(self.config, "donation_alerts_token", access_token)
            setattr(self.config, "donationalerts_refresh_token", new_refresh_token)
            if expires_in:
                from time import time as _time
                setattr(self.config, "donationalerts_expires_at", int(_time()) + int(expires_in))

            self.logger.info("Access token refreshed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Unexpected error refreshing token: {e}")
            return False
