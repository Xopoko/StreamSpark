import os
import types
import time
from pathlib import Path

import pytest
import core.state as state
from fastapi.testclient import TestClient
from typing import cast
from core.container import AppContainer

import main_fastapi


def make_container_with_vg(vg_stub):
    cfg = types.SimpleNamespace()
    cfg.videos_directory = "generated_videos"
    container = types.SimpleNamespace(
        config=cfg,
        currency_converter=types.SimpleNamespace(),
        video_generator=vg_stub,
        donation_poller=types.SimpleNamespace(),
        obs_widget=types.SimpleNamespace(),
    )
    return container


def test_generation_status_endpoint(client):
    class VG:
        def get_generation_status(self):
            return {"active": False, "progress": 42}

    container = make_container_with_vg(VG())
    state.set_container(cast(AppContainer, container))

    resp = client.get("/api/generation-status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data["status"], dict)
    assert data["status"]["progress"] == 42


def test_get_and_set_system_prompt(client):
    class VG:
        system_prompt = ""

    container = make_container_with_vg(VG())
    state.set_container(cast(AppContainer, container))

    # GET should return default or empty string
    resp = client.get("/api/system-prompt")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "prompt" in data

    # POST empty prompt -> error
    resp2 = client.post("/api/system-prompt", json={"prompt": ""})
    assert resp2.status_code == 200
    assert resp2.json()["success"] is False

    # POST valid prompt -> success and container updated
    resp3 = client.post("/api/system-prompt", json={"prompt": "Hello world"})
    assert resp3.status_code == 200
    assert resp3.json()["success"] is True
    assert container.video_generator.system_prompt == "Hello world"


def test_generate_custom_video_starts_background_and_uses_vg(client, monkeypatch):
    called = {"n": 0}

    class VG:
        def generate_video(self, donation_info, amount_rub, custom_prompt=None):
            called["n"] += 1
            return "/tmp/x.mp4"

    container = make_container_with_vg(VG())
    # set container so endpoint will use it
    state.set_container(cast(AppContainer, container))

    # Make Thread execute synchronously to avoid timing issues
    class ImmediateThread:
        def __init__(self, target=None, daemon=False):
            self._target = target

        def start(self):
            if self._target:
                self._target()

    monkeypatch.setattr("routes.api_generation.threading.Thread", ImmediateThread)

    resp = client.post("/api/generate-video", json={"prompt": "Make it fun"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    # Because ImmediateThread runs target synchronously, generation should have been invoked
    assert called["n"] == 1


def test_generate_veo_video_success_and_failure(client, tmp_path):
    # success case: video_generator returns a real file path
    video_file = tmp_path / "out.mp4"
    video_file.write_bytes(b"\x00\x01")

    class VGSuccess:
        def generate_video(self, donation_info, amount_rub, custom_prompt=None):
            return str(video_file)

    container_s = make_container_with_vg(VGSuccess())
    state.set_container(cast(AppContainer, container_s))

    resp = client.post("/api/generate-veo-video", json={"prompt": "Hello Veo"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "video_url" in data

    # failure case: generator returns None
    class VGFail:
        def generate_video(self, donation_info, amount_rub, custom_prompt=None):
            return None

    container_f = make_container_with_vg(VGFail())
    state.set_container(cast(AppContainer, container_f))

    resp2 = client.post("/api/generate-veo-video", json={"prompt": "Hello Veo"})
    assert resp2.status_code == 500
    data2 = resp2.json()
    assert data2["success"] is False
