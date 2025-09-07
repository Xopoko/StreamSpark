import time
import types
import threading
from datetime import datetime, timedelta

import pytest

from services.donation_alerts_client import DonationAlertsClient
from services.donation_alerts_poller import DonationAlertsPoller


class MockResp:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def test_donation_alerts_client_no_token():
    cfg = types.SimpleNamespace()
    client = DonationAlertsClient(cfg)
    assert client.fetch_donations() is None


def test_donation_alerts_client_fetch_success(monkeypatch):
    cfg = types.SimpleNamespace()
    client = DonationAlertsClient(cfg)
    client.set_api_token("token-123")

    # Mock requests.get to return a 200 with data
    def fake_get(url, headers=None, params=None, timeout=10):
        return MockResp(200, json_data={"data": [{"id": "d1"}]})

    monkeypatch.setattr("services.donation_alerts_client.requests.get", fake_get)

    donations = client.fetch_donations(page=1, limit=5)
    assert isinstance(donations, list)
    assert donations[0]["id"] == "d1"


def test_donation_alerts_client_401_then_refresh(monkeypatch):
    cfg = types.SimpleNamespace()
    # configure refresh tokens so refresh_access_token could run if needed
    cfg.donationalerts_client_id = "cid"
    cfg.donationalerts_client_secret = "csecret"
    cfg.donationalerts_refresh_token = "rtoken"

    client = DonationAlertsClient(cfg)
    # initial token set
    client.set_api_token("old-token")

    call_count = {"n": 0}

    def fake_get(url, headers=None, params=None, timeout=10):
        # first call -> 401, second call -> 200
        call_count["n"] += 1
        if call_count["n"] == 1:
            return MockResp(401, json_data={"error": "unauth"})
        return MockResp(200, json_data={"data": [{"id": "d2"}]})

    def fake_post(url, data=None, timeout=15):
        # Simulate token refresh response
        return MockResp(200, json_data={"access_token": "new-token", "refresh_token": "new-refresh", "expires_in": 3600})

    monkeypatch.setattr("services.donation_alerts_client.requests.get", fake_get)
    monkeypatch.setattr("services.donation_alerts_client.requests.post", fake_post)

    # Call fetch_donations, expecting the client to refresh and retry
    donations = client.fetch_donations()
    assert isinstance(donations, list)
    assert donations[0]["id"] == "d2"
    # ensure token was updated
    assert client.get_api_token() == "new-token"
    # config values updated
    assert cfg.donation_alerts_token or getattr(cfg, "donation_alerts_token", None) is not None


def test_refresh_access_token_missing_credentials():
    cfg = types.SimpleNamespace()
    client = DonationAlertsClient(cfg)
    # No client id/secret/refresh token -> refresh should fail
    assert client.refresh_access_token() is False


def test_refresh_access_token_success(monkeypatch):
    cfg = types.SimpleNamespace()
    cfg.donationalerts_client_id = "cid"
    cfg.donationalerts_client_secret = "csecret"
    cfg.donationalerts_refresh_token = "rtok"
    client = DonationAlertsClient(cfg)

    def fake_post(url, data=None, timeout=15):
        return MockResp(200, json_data={"access_token": "tokx", "refresh_token": "rtok2", "expires_in": 10})

    monkeypatch.setattr("services.donation_alerts_client.requests.post", fake_post)

    ok = client.refresh_access_token()
    assert ok is True
    assert client.get_api_token() == "tokx"
    assert getattr(cfg, "donationalerts_refresh_token", None) == "rtok2"


def test_poller_is_test_detection_and_parsing():
    cfg = types.SimpleNamespace()
    conv = types.SimpleNamespace()
    vg = types.SimpleNamespace()
    poller = DonationAlertsPoller(cfg, conv, vg)

    # is_test detection via different keys
    assert poller._is_test_donation({"is_test": True}) is True
    assert poller._is_test_donation({"isTest": 1}) is True
    assert poller._is_test_donation({"type": "test"}) is True
    # ambiguous structure returns True by fail-safe when error triggered; regular donation returns False
    assert poller._is_test_donation({"id": "x"}) is False

    # parse created_at ISO and format
    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    parsed = poller._parse_created_at(now)
    assert parsed is not None

    s = "2025-09-07 00:00:00"
    parsed2 = poller._parse_created_at(s)
    assert parsed2 is not None

    # freshness: recent datetime -> True, old -> False
    recent = datetime.now()
    assert poller._is_fresh(recent, window_minutes=5) is True
    old = datetime.now() - timedelta(minutes=10)
    assert poller._is_fresh(old, window_minutes=5) is False


def test_process_single_donation_qualifies_and_generates(monkeypatch):
    # Prepare config with low threshold to easily qualify
    cfg = types.SimpleNamespace()
    cfg.donation_threshold_rub = 100.0

    # Stub currency converter (passthrough)
    class ConvStub:
        def convert_to_rub(self, amount, cur):
            return float(amount)

    generated = {"count": 0}

    class VGStub:
        def generate_video(self, donation_info, amount_rub):
            generated["count"] += 1
            return "/tmp/video.mp4"

    conv = ConvStub()
    vg = VGStub()
    poller = DonationAlertsPoller(cfg, conv, vg)

    # Ensure no threading delays: patch threading.Thread so start() calls target immediately
    class ImmediateThread:
        def __init__(self, target=None, daemon=False):
            self._target = target

        def start(self):
            if self._target:
                self._target()

    monkeypatch.setattr("services.donation_alerts_poller.threading.Thread", ImmediateThread)

    donation = {
        "id": "don1",
        "username": "A",
        "amount": 150,
        "currency": "RUB",
        "message": "hi",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    poller._process_single_donation(donation)
    # Donation should be recorded as processed and generation triggered
    assert "don1" in poller.processed_donations
    # generation happened synchronously due to ImmediateThread
    assert generated["count"] == 1
    assert poller.total_donations_processed == 1
    assert poller.total_videos_generated == 1


def test_process_single_donation_skips_test_and_stale(monkeypatch):
    cfg = types.SimpleNamespace()
    cfg.donation_threshold_rub = 10.0
    conv = types.SimpleNamespace()
    vg = types.SimpleNamespace()
    poller = DonationAlertsPoller(cfg, conv, vg)

    # test donation is skipped
    td = {"id": "t1", "is_test": True, "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    poller._process_single_donation(td)
    assert "t1" in poller.processed_donations

    # stale donation skipped
    stale = {"id": "s1", "created_at": (datetime.now() - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")}
    poller._process_single_donation(stale)
    assert "s1" in poller.processed_donations


def test_test_api_connection_and_stats(monkeypatch):
    cfg = types.SimpleNamespace()
    conv = types.SimpleNamespace()
    vg = types.SimpleNamespace()
    poller = DonationAlertsPoller(cfg, conv, vg)

    # If no token, test_api_connection returns failure dict
    res = poller.test_api_connection()
    assert res["success"] is False

    # If token is set and _fetch_donations returns a list, should return success
    poller.api_token = "tok"
    monkeypatch.setattr(poller, "_fetch_donations", lambda: [{"id": "x"}, {"id": "y"}])
    res2 = poller.test_api_connection()
    assert res2["success"] is True
    assert res2["total_donations"] == 2

    # Stats reflect internal counters
    st = poller.get_stats()
    assert "is_running" in st and "has_token" in st
