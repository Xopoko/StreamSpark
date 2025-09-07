import types
import time
from datetime import datetime
import pytest
import core.state as state
from typing import cast
from core.container import AppContainer

# Reuse client fixture from tests/conftest.py
# Tests for routes/api_settings.py


def make_container(cfg_overrides=None):
    cfg = types.SimpleNamespace()
    cfg.donation_alerts_token = ""
    cfg.donation_threshold_amount = 1000.0
    cfg.donation_threshold_currency = "RUB"
    cfg.donation_threshold_rub = 1000.0
    if cfg_overrides:
        for k, v in cfg_overrides.items():
            setattr(cfg, k, v)

    # Simple stubs for services
    class PollerStub:
        def __init__(self):
            self.is_running = False
            self.total_donations_processed = 0
            self.total_videos_generated = 0
            self.last_poll_time = None

        def set_api_token(self, token):
            self._token = token

        def start_polling(self):
            self.is_running = True

        def stop_polling(self):
            self.is_running = False

    container = types.SimpleNamespace(
        config=cfg,
        currency_converter=types.SimpleNamespace(convert_to_rub=lambda a, c: float(a) if c == "RUB" else float(a) * 70.0),
        video_generator=types.SimpleNamespace(client=types.SimpleNamespace(has_api_key=lambda: True), system_prompt=""),
        donation_poller=PollerStub(),
        obs_widget=types.SimpleNamespace(),
    )
    return container


def test_get_settings_and_connection_status(client):
    c = make_container()
    state.set_container(cast(AppContainer, c))

    r = client.get("/api/settings")
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert "donation_alerts_token" in data

    r2 = client.get("/api/connection-status")
    assert r2.status_code == 200
    c2 = r2.json()
    assert "configured" in c2 and "connected" in c2


def test_set_donation_alerts_token_starts_and_stops_poller(client, monkeypatch):
    c = make_container()
    state.set_container(cast(AppContainer, c))

    # initially no token
    resp = client.post("/api/donation-alerts-token", json={"token": ""})
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # set a token -> should attempt to start poller
    resp2 = client.post("/api/donation-alerts-token", json={"token": "abc"})
    assert resp2.status_code == 200
    assert resp2.json()["success"] is True
    assert c.donation_poller.is_running is True

    # clear token -> should stop poller
    resp3 = client.post("/api/donation-alerts-token", json={"token": ""})
    assert resp3.status_code == 200
    assert resp3.json()["success"] is True
    assert c.donation_poller.is_running is False


def test_get_and_set_threshold_with_conversion(client):
    # container with currency conversion behavior
    c = make_container()
    state.set_container(cast(AppContainer, c))

    # GET threshold
    r = client.get("/api/threshold")
    assert r.status_code == 200
    assert "threshold" in r.json()

    # POST positive threshold in RUB
    r2 = client.post("/api/threshold", json={"threshold": 500})
    assert r2.status_code == 200
    assert r2.json()["success"] is True
    assert c.config.donation_threshold_rub == 500.0

    # POST threshold in USD -> conversion via stub (70x)
    r3 = client.post("/api/threshold", json={"amount": 10, "currency": "USD"})
    assert r3.status_code == 200
    assert r3.json()["success"] is True
    # 10 USD -> 700 RUB via stubbed convert_to_rub
    assert c.config.donation_threshold_rub == pytest.approx(700.0)


def test_access_token_endpoints(client):
    c = make_container()
    state.set_container(cast(AppContainer, c))

    # Initially no token
    r = client.get("/api/access-token")
    assert r.status_code == 200
    assert r.json()["has_token"] is False

    # Set access token
    r2 = client.post("/api/access-token", json={"access_token": "tok-1"})
    assert r2.status_code == 200
    assert r2.json()["success"] is True
    assert c.config.donation_alerts_token == "tok-1"
    assert c.donation_poller.is_running is True

    # Clear access token
    r3 = client.post("/api/access-token", json={"access_token": ""})
    assert r3.status_code == 200
    assert r3.json()["success"] is True
    assert c.donation_poller.is_running is False


def test_aiml_status_endpoint(client):
    c = make_container()
    # set some poller stats
    c.donation_poller.total_donations_processed = 5
    c.donation_poller.total_videos_generated = 2
    c.donation_poller.last_poll_time = datetime.now()
    state.set_container(cast(AppContainer, c))

    r = client.get("/api/aiml-status")
    assert r.status_code == 200
    j = r.json()
    assert j["success"] is True
    assert "has_api_key" in j
    assert j["total_donations_processed"] == 5
