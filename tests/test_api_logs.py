import time
import types
from datetime import datetime
import pytest
import core.state as state
import core.logging_utils as logging_utils
from typing import cast
from core.container import AppContainer

# Reuse client fixture


def make_container_with_poller_stats(tmp_path):
    cfg = types.SimpleNamespace()
    cfg.videos_directory = str(tmp_path)
    class PollerStub:
        def __init__(self):
            self.is_running = False
            self.total_donations_processed = 3
            self.total_videos_generated = 1
            self.last_poll_time = datetime.now()

        def get_stats(self):
            return {
                "is_running": self.is_running,
                "has_token": False,
                "total_donations_processed": self.total_donations_processed,
                "total_videos_generated": self.total_videos_generated,
                "last_poll_time": (self.last_poll_time.isoformat() if self.last_poll_time else None),
                "api_errors": 0,
            }

    container = types.SimpleNamespace(
        config=cfg,
        donation_poller=PollerStub(),
        currency_converter=types.SimpleNamespace(),
        video_generator=types.SimpleNamespace(),
        obs_widget=types.SimpleNamespace(),
    )
    return container


def test_parse_access_log_and_get_logs_endpoint(client, monkeypatch):
    # Create fake log entries including uvicorn.access style message
    ts = int(time.time() * 1000)
    access_msg = '127.0.0.1:12345 - "GET /api/stats HTTP/1.1" 200'
    general_msg = 'Some general log message'

    fake_entries = [
        {"timestamp": ts, "level": "INFO", "logger": "uvicorn.access", "message": access_msg},
        {"timestamp": ts + 1, "level": "ERROR", "logger": "app.module", "message": general_msg},
    ]

    # Patch get_recent_logs to return our fake entries (patch the imported name used by the logs route)
    monkeypatch.setattr("routes.api_logs.get_recent_logs", lambda since_ms=0: fake_entries)

    # Call endpoint without show_ip
    r = client.get("/api/logs")
    assert r.status_code == 200
    j = r.json()
    assert j["success"] is True
    assert isinstance(j["logs"], list)
    # Ensure uvicorn access entry parsed as http type
    assert any(l.get("type") == "http" for l in j["logs"])

    # Call endpoint with show_ip and ensure ip field present
    r2 = client.get("/api/logs?show_ip=true")
    j2 = r2.json()
    assert any("ip" in l for l in j2["logs"])


def test_stats_endpoint_returns_counts_and_uses_polling_stats(tmp_path, client):
    container = make_container_with_poller_stats(tmp_path)
    # create a video file to be counted
    (tmp_path / "sample.mp4").write_bytes(b"\x00")
    state.set_container(cast(AppContainer, container))

    r = client.get("/api/stats")
    assert r.status_code == 200
    j = r.json()
    assert "totalVideos" in j
    assert j["totalVideos"] >= 1
    assert "totalDonations" in j
