import os
import time
from pathlib import Path

import pytest

from services.obs_widget import OBSWidget


def create_video_file(directory: Path, name: str, size: int = 10):
    os.makedirs(directory, exist_ok=True)
    path = directory / name
    with open(path, "wb") as f:
        f.write(b"\x00" * size)
    # modify creation time slightly
    return path


def test_list_and_latest_video(tmp_path):
    videos_dir = tmp_path / "videos"
    videos_dir.mkdir()
    # Create two mp4 files with different ctimes
    f1 = create_video_file(videos_dir, "a_older.mp4", size=4)
    time.sleep(0.01)
    f2 = create_video_file(videos_dir, "b_newer.mp4", size=8)

    obs = OBSWidget()
    # point widget to our temp dir
    obs.videos_directory = str(videos_dir)

    lst = obs.list_videos()
    assert isinstance(lst, list)
    # newest should be first
    assert lst[0]["filename"] == "b_newer.mp4"
    status = obs.get_widget_status()
    assert status["total_videos"] == 2
    assert status["latest_video"] == "b_newer.mp4"


def test_resolve_and_safe_filename(tmp_path):
    videos_dir = tmp_path / "videos"
    videos_dir.mkdir()
    file = create_video_file(videos_dir, "safe-name.mp4", size=2)

    obs = OBSWidget()
    obs.videos_directory = str(videos_dir)

    resolved = obs.resolve_video_path("safe-name.mp4")
    assert resolved is not None and resolved.endswith("safe-name.mp4")

    # unsafe filename
    assert obs.resolve_video_path("../secret.mp4") is None
    assert obs._is_safe_filename("bad/name.mp4") is False


def test_get_latest_with_request_ttl(tmp_path):
    videos_dir = tmp_path / "videos"
    videos_dir.mkdir()
    file = create_video_file(videos_dir, "only.mp4", size=2)

    obs = OBSWidget()
    obs.videos_directory = str(videos_dir)

    # create play request with current timestamp
    obs._play_request = {"filename": "only.mp4", "ts": int(time.time())}
    data = obs.get_latest_video_data()
    assert data["status"] == "success"
    assert data["requested"] is True

    # expired request should fall back to latest
    obs._play_request = {"filename": "only.mp4", "ts": int(time.time()) - 20}
    data2 = obs.get_latest_video_data()
    assert data2["requested"] is False
