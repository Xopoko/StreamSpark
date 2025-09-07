import os
import time
import types
import pytest
from services.aiml_client import AIMLClient

class MockResp:
    def __init__(self, status_code=200, json_data=None, text="", content=b""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text
        self._content = content
        self._iter_called = False

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size=8192):
        # yield the content in a single chunk for tests
        if self._iter_called:
            return
        self._iter_called = True
        yield self._content


def test_start_generation_success(monkeypatch):
    client = AIMLClient(api_key="key")

    def fake_post(url, json=None, headers=None, timeout=30):
        return MockResp(200, json_data={"id": "gen-1"})

    monkeypatch.setattr("services.aiml_client.requests.post", fake_post)

    gen_id = client.start_generation("hello")
    assert gen_id == "gen-1"


def test_start_generation_failure(monkeypatch):
    client = AIMLClient(api_key="key")

    def fake_post(url, json=None, headers=None, timeout=30):
        return MockResp(500, json_data={"error": "fail"}, text="error")

    monkeypatch.setattr("services.aiml_client.requests.post", fake_post)

    gen_id = client.start_generation("hello")
    assert gen_id is None


def test_wait_for_completion_completed(monkeypatch):
    client = AIMLClient(api_key="key")

    calls = {"n": 0}
    # first call: generating, second call: completed with video
    def fake_get(url, params=None, headers=None, timeout=30):
        calls["n"] += 1
        if calls["n"] == 1:
            return MockResp(200, json_data={"status": "generating"})
        return MockResp(200, json_data={"status": "completed", "video": {"url": "http://example.com/v.mp4"}})

    monkeypatch.setattr("services.aiml_client.requests.get", fake_get)

    recorded = []
    def progress_cb(info):
        recorded.append(info)

    # Use small poll interval to avoid long sleeps
    url = client.wait_for_completion("gen-1", max_wait_time=2, poll_interval=0, progress_callback=progress_cb)
    assert url == "http://example.com/v.mp4"
    # Ensure progress callback was invoked at least twice (poll + completed)
    assert any(i.get("phase") == "completed" for i in recorded)


def test_wait_for_completion_error_status(monkeypatch):
    client = AIMLClient(api_key="key")

    def fake_get(url, params=None, headers=None, timeout=30):
        return MockResp(200, json_data={"status": "failed"})

    monkeypatch.setattr("services.aiml_client.requests.get", fake_get)

    res = client.wait_for_completion("gen-x", max_wait_time=1, poll_interval=0)
    assert res is None


def test_wait_for_completion_timeout(monkeypatch):
    client = AIMLClient(api_key="key")

    def fake_get(url, params=None, headers=None, timeout=30):
        return MockResp(200, json_data={"status": "generating"})

    monkeypatch.setattr("services.aiml_client.requests.get", fake_get)
    # avoid sleeping for real
    monkeypatch.setattr("time.sleep", lambda s: None)

    res = client.wait_for_completion("gen-timeout", max_wait_time=0.05, poll_interval=0)
    assert res is None


def test_download_video_success(monkeypatch, tmp_path):
    client = AIMLClient(api_key="key")

    content = b"VIDEO_BYTES"
    def fake_get(url, stream=True, timeout=60):
        return MockResp(200, json_data={}, content=content)

    monkeypatch.setattr("services.aiml_client.requests.get", fake_get)

    local = str(tmp_path / "out.mp4")
    ok = client.download_video("http://example.com/v.mp4", local)
    assert ok is True
    assert os.path.exists(local)
    assert os.path.getsize(local) == len(content)


def test_download_video_fail(monkeypatch, tmp_path):
    client = AIMLClient(api_key="key")

    def fake_get_fail(url, stream=True, timeout=60):
        return MockResp(500, text="Server error")

    monkeypatch.setattr("services.aiml_client.requests.get", fake_get_fail)

    local = str(tmp_path / "out2.mp4")
    ok = client.download_video("http://example.com/v.mp4", local)
    assert ok is False
    assert not os.path.exists(local)
