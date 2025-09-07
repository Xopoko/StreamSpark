import types
import time
import urllib.parse
import pytest
import core.state as state
from typing import cast
from core.container import AppContainer

class MockResp:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self):
        return self._json


def make_container_for_oauth():
    cfg = types.SimpleNamespace()
    # defaults empty; tests will override as needed
    cfg.donationalerts_client_id = None
    cfg.donationalerts_client_secret = None
    cfg.donationalerts_redirect_uri = None
    cfg.donation_alerts_token = ""
    cfg.donationalerts_refresh_token = ""
    cfg.donationalerts_token_type = ""
    cfg.donationalerts_expires_at = 0

    class PollerStub:
        def __init__(self):
            self.is_running = False
            self._token = None

        def set_api_token(self, token):
            self._token = token

        def start_polling(self):
            self.is_running = True

        def stop_polling(self):
            self.is_running = False

    container = types.SimpleNamespace(
        config=cfg,
        donation_poller=PollerStub(),
        currency_converter=types.SimpleNamespace(),
        video_generator=types.SimpleNamespace(),
        obs_widget=types.SimpleNamespace(),
    )
    return container


def test_oauth_login_missing_config(client):
    c = make_container_for_oauth()
    state.set_container(cast(AppContainer, c))

    r = client.get("/api/da/oauth/login")
    assert r.status_code == 400
    j = r.json()
    assert j["success"] is False
    assert "missing" in j


def test_oauth_callback_missing_code(client):
    c = make_container_for_oauth()
    state.set_container(cast(AppContainer, c))

    r = client.get("/api/da/oauth/callback")
    assert r.status_code == 400
    j = r.json()
    assert j["success"] is False


def test_oauth_callback_success_and_disconnect(monkeypatch, client):
    c = make_container_for_oauth()
    # configure oauth values
    c.config.donationalerts_client_id = "cid"
    c.config.donationalerts_client_secret = "csecret"
    c.config.donationalerts_redirect_uri = "http://localhost:5002/api/da/oauth/callback"
    state.set_container(cast(AppContainer, c))

    # mock token exchange
    def fake_post(url, data=None, timeout=15):
        return MockResp(200, json_data={"access_token": "at-1", "refresh_token": "rt-1", "expires_in": 3600})

    monkeypatch.setattr("routes.donation_alerts_oauth.requests.post", fake_post)

    r = client.get("/api/da/oauth/callback?code=abc123&state=zzz")
    # Should redirect to /dashboard (TestClient may follow redirects; accept 3xx or final 200)
    assert r.status_code in (301, 302, 307, 308, 200)
    # Ensure the access token was applied to config
    assert c.config.donation_alerts_token == "at-1"

    # Now test disconnect
    r2 = client.post("/api/da/disconnect")
    assert r2.status_code == 200
    j2 = r2.json()
    assert j2["success"] is True
    assert c.config.donation_alerts_token == ""
