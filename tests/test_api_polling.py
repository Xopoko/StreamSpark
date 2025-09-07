import types
import time
from datetime import datetime
import pytest
import core.state as state

# Tests for routes/api_polling.py


def make_container_with_poller(recents=None, test_conn_success=False):
    cfg = types.SimpleNamespace()
    cfg.donation_alerts_token = ""

    class PollerStub:
        def __init__(self):
            self.is_running = False
            self._recents = recents or []
            self.total_donations_processed = 0
            self.total_videos_generated = 0
            self.last_poll_time = None
            self.api_errors = 0

        def get_recent_donations(self, limit=50):
            return list(self._recents[:limit])

        def test_api_connection(self):
            if test_conn_success:
                # return a dict similar to real method
                return {"success": True, "status": "Connected", "data": [], "api_errors": 0}
            else:
                return {"success": False, "error": "failed"}

        def start_polling(self):
            self.is_running = True

        def stop_polling(self):
            self.is_running = False

    container = types.SimpleNamespace(
        config=cfg,
        currency_converter=types.SimpleNamespace(),
        video_generator=types.SimpleNamespace(),
        donation_poller=PollerStub(),
        obs_widget=types.SimpleNamespace(),
    )
    return container


def test_get_donations_transforms_and_returns(client):
    # Recent donations returned by poller should be transformed by endpoint
    recents = [
        {"id": "d1", "username": "Alice", "amount": 10, "currency": "USD", "message": "Hi", "created_at": "now"},
        {"id": "d2", "username": "Bob", "amount": 5, "currency": "RUB", "message": "", "created_at": "now2"},
    ]
    c = make_container_with_poller(recents=recents)
    state.set_container(c)

    r = client.get("/api/donations?limit=2")
    assert r.status_code == 200
    j = r.json()
    assert j["success"] is True
    assert isinstance(j["donations"], list)
    assert any(d["id"] == "d1" for d in j["donations"])


def test_test_donation_alerts_starts_polling_on_success(client):
    c = make_container_with_poller(recents=[], test_conn_success=True)
    state.set_container(c)

    r = client.get("/api/test-donation-alerts")
    assert r.status_code == 200
    j = r.json()
    assert j.get("success") is True
    # Poller should have been started by endpoint
    assert c.donation_poller.is_running is True


def test_test_donation_alerts_failure_does_not_start(client):
    c = make_container_with_poller(recents=[], test_conn_success=False)
    state.set_container(c)

    r = client.get("/api/test-donation-alerts")
    assert r.status_code == 200
    j = r.json()
    assert j.get("success") is False
    assert c.donation_poller.is_running is False


def test_start_stop_polling_endpoints_respect_token_and_toggle(client):
    c = make_container_with_poller()
    # no token configured -> start should fail
    state.set_container(c)
    resp = client.post("/api/start-polling")
    assert resp.status_code == 200
    assert resp.json()["success"] is False

    # configure token and start
    c.config.donation_alerts_token = "tok-1"
    resp2 = client.post("/api/start-polling")
    assert resp2.status_code == 200
    assert resp2.json()["success"] is True
    assert c.donation_poller.is_running is True

    # stop polling
    resp3 = client.post("/api/stop-polling")
    assert resp3.status_code == 200
    assert resp3.json()["success"] is True
    assert c.donation_poller.is_running is False
