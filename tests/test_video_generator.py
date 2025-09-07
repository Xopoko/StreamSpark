import os
import types
import time
from pathlib import Path

import pytest

from services.video_generator import VideoGenerator

class AIMLStub:
    def __init__(self, api_key=None, logger=None):
        self.api_key = api_key
        self.logger = logger

    def has_api_key(self):
        return True

    def start_generation(self, prompt: str):
        return "gen-123"

    def wait_for_completion(self, generation_id: str, progress_callback=None):
        # Simulate returning a remote URL
        if generation_id == "gen-123":
            # Optionally call progress callback to simulate progress updates
            if progress_callback:
                progress_callback({"status": "generating", "elapsed": 1})
                progress_callback({"status": "downloading", "video_url": "http://example.com/video.mp4"})
            return "http://example.com/video.mp4"
        return None

    def download_video(self, video_url: str, local_path: str):
        # Simulate download by creating a small file
        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(b"\x00\x01")
            return True
        except Exception:
            return False


def make_config(tmp_path: Path):
    cfg = types.SimpleNamespace()
    cfg.videos_directory = str(tmp_path / "videos")
    cfg.get_video_prompt = lambda amount: f"Prompt for {amount}"
    return cfg


def test_generate_video_success(monkeypatch, tmp_path):
    # Replace AIMLClient used internally with our stub
    monkeypatch.setattr("services.video_generator.AIMLClient", AIMLStub)

    cfg = make_config(tmp_path)
    vg = VideoGenerator(cfg)

    donation_info = {"username": "Tester", "message": "Awesome!"}
    # Call generate_video and expect a path returned and file created
    path = vg.generate_video(donation_info, 1500.0, custom_prompt=None)
    assert path is not None
    assert os.path.exists(path)
    assert vg.get_latest_video_path() == path

    # list_generated_videos should include our generated file
    videos = vg.list_generated_videos()
    assert any(v["path"] == path for v in videos)


def test_generate_video_download_failure(monkeypatch, tmp_path):
    # Stub that starts generation but fails download
    class AIMLFailDownload(AIMLStub):
        def download_video(self, video_url: str, local_path: str):
            return False

    monkeypatch.setattr("services.video_generator.AIMLClient", AIMLFailDownload)
    cfg = make_config(tmp_path)
    vg = VideoGenerator(cfg)

    donation_info = {"username": "NoDownload", "message": "x"}
    path = vg.generate_video(donation_info, 2000.0)
    # Because download failed, generate_video should return None
    assert path is None
    assert vg.get_latest_video_path() is None


def test_get_generation_status_mapping(monkeypatch, tmp_path):
    monkeypatch.setattr("services.video_generator.AIMLClient", AIMLStub)
    cfg = make_config(tmp_path)
    vg = VideoGenerator(cfg)

    # Initially idle
    status = vg.get_generation_status()
    assert status["progress"] == 0 or isinstance(status["progress"], int)

    # Simulate active_generation states and verify mapping
    vg.active_generation = {"active": True, "status": "generating"}
    status = vg.get_generation_status()
    assert status["progress"] == 70

    vg.active_generation = {"active": True, "status": "downloading"}
    status = vg.get_generation_status()
    assert status["progress"] == 90

    vg.active_generation = {"active": False, "status": "done"}
    status = vg.get_generation_status()
    assert status["progress"] == 100
