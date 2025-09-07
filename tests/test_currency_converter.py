import time
import types
import pytest
from services.currency_converter import CurrencyConverter


class MockResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self):
        return self._json

    def raise_for_status(self):
        """Mimic requests.Response.raise_for_status() — no-op for status_code 200."""
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")
        return None


def test_convert_to_rub_when_already_rub():
    conv = CurrencyConverter()
    assert conv.convert_to_rub(123.45, "RUB") == pytest.approx(123.45)


def test_convert_to_rub_uses_api_and_caches(monkeypatch):
    conv = CurrencyConverter()

    # Prepare mock response for free API (structure: {"rates": {"RUB": rate}})
    mock_json = {"rates": {"RUB": 70.0}}
    def fake_get(url, timeout=10):
        return MockResponse(status_code=200, json_data=mock_json)

    monkeypatch.setattr("services.currency_converter.requests.get", fake_get)

    result = conv.convert_to_rub(10, "USD")  # expect 10 * 70 = 700
    assert result == pytest.approx(700.0)

    # Ensure rate cached
    cached = conv._get_cached_rate("USD", "RUB")
    assert cached == pytest.approx(70.0)

    # Simulate expiry by setting cache expiry in the past and ensure it's dropped
    key = ("USD", "RUB")
    if key in conv._cache:
        rate, expires = conv._cache[key]
        conv._cache[key] = (rate, time.time() - 10.0)
    expired = conv._get_cached_rate("USD", "RUB")
    assert expired is None


def test_fetch_exchange_rate_api_failure(monkeypatch):
    conv = CurrencyConverter()

    def fake_get_fail(url, timeout=10):
        return MockResponse(status_code=500, json_data={"error": "bad"}, text="Server Error")

    monkeypatch.setattr("services.currency_converter.requests.get", fake_get_fail)

    # When API fails, conversion should return None
    result = conv.convert_to_rub(5, "EUR")
    assert result is None


def test__fetch_exchange_rates_free_api(monkeypatch):
    conv = CurrencyConverter()

    # Build a fake USD rates payload including RUB
    usd_rates = {"RUB": 70.0, "EUR": 0.9, "GBP": 0.8}
    def fake_get(url, timeout=10):
        return MockResponse(status_code=200, json_data={"rates": usd_rates})

    monkeypatch.setattr("services.currency_converter.requests.get", fake_get)

    rates = conv._fetch_exchange_rates()
    assert isinstance(rates, dict)
    assert "USD_RUB" in rates or "EUR_RUB" in rates
    # USD_RUB should equal rub_per_usd (70.0)
    assert pytest.approx(rates.get("USD_RUB", 70.0)) == 70.0


def test_get_supported_currencies_contains_rub():
    conv = CurrencyConverter()
    supported = conv.get_supported_currencies()
    assert "RUB" in supported


def test_health_check_success(monkeypatch):
    conv = CurrencyConverter()
    # Mock convert_to_rub to return a positive value
    monkeypatch.setattr(conv, "convert_to_rub", lambda amount, cur: 70.0)
    assert conv.health_check() is True

def test_health_check_failure(monkeypatch):
    conv = CurrencyConverter()
    # Mock convert_to_rub to return None
    monkeypatch.setattr(conv, "convert_to_rub", lambda amount, cur: None)
    assert conv.health_check() is False
