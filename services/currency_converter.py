"""
Currency conversion service using live exchange rates with in-memory TTL cache.
Converts donation amounts to RUB for threshold checking. No database is used.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

import requests


class CurrencyConverter:
    """Service for converting currencies to RUB using live exchange rates with in-memory caching."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # API key and endpoints
        # Use free tier only; no environment variables
        self.api_key = None
        self.api_base = "https://api.exchangerate-api.com/v4/latest"
        self.logger.info("Using free exchange rate API (no API key)")

        # In-memory cache: { (from, to): (rate, expires_at_unix) }
        self._cache: Dict[Tuple[str, str], Tuple[float, float]] = {}

        # Cache TTL (minutes), read once on startup; default 5 minutes
        self._cache_ttl_minutes = self._get_cache_duration()

        self.logger.info("CurrencyConverter initialized with in-memory caching")

    def convert_to_rub(self, amount: float, from_currency: str) -> Optional[float]:
        """Convert amount from given currency to RUB."""
        try:
            from_currency = (from_currency or "RUB").upper()
            if from_currency == "RUB":
                return float(amount)

            # Get exchange rate
            rate = self._get_exchange_rate(from_currency, "RUB")
            if rate is None:
                self.logger.error(f"Could not get exchange rate for {from_currency} to RUB")
                return None

            converted_amount = float(amount) * rate
            self.logger.info(f"Converted {amount} {from_currency} to {converted_amount:.2f} RUB (rate: {rate})")
            return converted_amount
        except Exception as e:
            self.logger.error(f"Error converting currency: {e}")
            return None

    def _get_exchange_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Get exchange rate from in-memory cache or API."""
        try:
            # Try in-memory cache
            cached = self._get_cached_rate(from_currency, to_currency)
            if cached is not None:
                return cached

            # Fetch from API and cache
            rate = self._fetch_exchange_rate_from_api(from_currency, to_currency)
            return rate
        except Exception as e:
            self.logger.error(f"Error getting exchange rate: {e}")
            return None

    def _get_cached_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Return cached exchange rate if not expired."""
        key = (from_currency, to_currency)
        now = time.time()
        cached = self._cache.get(key)
        if not cached:
            return None
        rate, expires_at = cached
        if now < expires_at:
            self.logger.debug(f"Using cached rate for {from_currency}->{to_currency}: {rate}")
            return rate
        # Expired - drop it
        try:
            del self._cache[key]
        except KeyError:
            pass
        return None

    def _fetch_exchange_rate_from_api(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Fetch exchange rate from API and cache in memory."""
        try:
            if self.api_key:
                # Paid API
                url = f"{self.api_base}/latest/{from_currency}"
            else:
                # Free API
                url = f"{self.api_base}/{from_currency}"

            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                self.logger.error(f"API request failed: {response.status_code} - {response.text}")
                return None

            data = response.json()
            if self.api_key and "conversion_rates" in data:
                rate = data["conversion_rates"].get(to_currency)
            else:
                # Free API structure
                rate = (data.get("rates") or {}).get(to_currency)

            if rate is None:
                self.logger.error(f"Rate for {to_currency} not found in API response")
                return None

            rate = float(rate)
            self._cache_exchange_rate(from_currency, to_currency, rate)
            return rate
        except requests.RequestException as e:
            self.logger.error(f"API request error: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error fetching exchange rate: {e}")
            return None

    def _get_cache_duration(self) -> int:
        """Get cache duration (fixed)."""
        return 5

    def _cache_exchange_rate(self, from_currency: str, to_currency: str, rate: float) -> None:
        """Cache exchange rate in memory with TTL."""
        ttl_minutes = self._cache_ttl_minutes
        expires_at = time.time() + ttl_minutes * 60.0
        self._cache[(from_currency, to_currency)] = (rate, expires_at)
        self.logger.debug(
            f"Cached exchange rate: {from_currency}->{to_currency} = {rate} (ttl {ttl_minutes} min)"
        )

    def _fetch_exchange_rates(self) -> Optional[dict]:
        """Fetch multiple exchange rates (optional helper)."""
        try:
            if self.api_key:
                # Use paid API with RUB as base
                url = f"{self.api_base}/latest/RUB"
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()

                if data.get("result") == "success":
                    rates = {}
                    # Convert rates to RUB (inverse of rates from RUB)
                    for currency, rate in data["conversion_rates"].items():
                        if currency != "RUB" and rate > 0:
                            rates[f"{currency}_RUB"] = 1.0 / rate

                    rates["RUB_RUB"] = 1.0
                    return rates
                else:
                    self.logger.error(f"API error: {data.get('error-type', 'Unknown error')}")
                    return None
            else:
                # Use free API
                url = f"{self.api_base}/USD"  # Get USD base rates
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()

                usd_rates = data.get("rates", {})
                rub_per_usd = usd_rates.get("RUB")

                if not rub_per_usd:
                    self.logger.error("Could not get USD to RUB rate")
                    return None

                # Calculate rates to RUB via USD
                rates = {}
                for currency, usd_rate in usd_rates.items():
                    if currency != "RUB" and usd_rate > 0:
                        # Currency -> USD -> RUB
                        rub_rate = rub_per_usd / usd_rate
                        rates[f"{currency}_RUB"] = rub_rate

                rates["RUB_RUB"] = 1.0
                rates["USD_RUB"] = rub_per_usd
                return rates
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error fetching exchange rates: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error parsing exchange rate data: {e}")
            return None

    def get_supported_currencies(self) -> list:
        """Get list of supported currencies."""
        # Common currencies that should be supported
        return [
            "USD",
            "EUR",
            "GBP",
            "JPY",
            "AUD",
            "CAD",
            "CHF",
            "CNY",
            "SEK",
            "NOK",
            "MXN",
            "SGD",
            "HKD",
            "KRW",
            "TRY",
            "PLN",
            "CZK",
            "HUF",
            "ILS",
            "CLP",
            "PHP",
            "AED",
            "SAR",
            "MYR",
            "THB",
            "UAH",
            "KZT",
            "BYN",
            "RUB",
        ]

    def health_check(self) -> bool:
        """Check if currency conversion service is working."""
        try:
            # Try to convert 1 USD to RUB
            result = self.convert_to_rub(1.0, "USD")
            return result is not None and result > 0
        except Exception:
            return False
