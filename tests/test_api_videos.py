import os
import types
import time
from pathlib import Path

import pytest
import core.state as state

# Reuse client fixture from tests/conftest.py


def make_container_with_obs(videos_dir: Path):
    cfg = types.SimpleNamespace()
    cfg.videos_directory = str(videos_dir)

    # create a real OBSWidget-like stub that uses videos_dir
    class ObsStub:
        def __init__(self, vd):
            self.videos_directory = str(vd)
            self._play_request = None

        def list_videos(self):
            videos = []
            if os.path.exists(self.videos_directory):
                for fn in os.listdir(self.videos_directory):
                    if fn.endswith(".mp4"):
                        p = os.path.join(self.videos_directory, fn)
                        videos.append({"filename": fn, "path": p, "size": os.path.getsize(p), "created": os.path.getctime(p)})
            videos.sort(key=lambda x: x["created"], reverse=True)
            return videos

        def resolve_video_path(self, filename):
            p = os.path.join(self.videos_directory, filename)
            if os.path.exists(p):
                return os.path.abspath(p)
            return None

    container = types.SimpleNamespace(
        config=cfg,
        currency_converter=types.SimpleNamespace(),
        video_generator=types.SimpleNamespace(),
        donation_poller=types.SimpleNamespace(),
        obs_widget=ObsStub(videos_dir),
    )
    return container


def test_recent_and_all_videos_and_delete_and_play(client, tmp_path):
    videos_dir = tmp_path / "videos"
    videos_dir.mkdir()

    # create files
    f1 = videos_dir / "one.mp4"
    f1.write_bytes(b"\x00" * 10)
    time.sleep(0.01)
    f2 = videos_dir / "two.mp4"
    f2.write_bytes(b"\x00" * 20)

    container = make_container_with_obs(videos_dir)
    state.set_container(container)

    # recent videos
    r = client.get("/api/recent-videos")
    assert r.status_code == 200
    jr = r.json()
    assert jr["success"] is True
    assert isinstance(jr["videos"], list)
    assert any(v["filename"] == "two.mp4" for v in jr["videos"])

    # all videos
    r2 = client.get("/api/all-videos")
    assert r2.status_code == 200
    ja = r2.json()
    assert ja["success"] is True
    assert len(ja["videos"]) >= 2

    # play-in-obs by filename
    resp = client.post("/api/play-in-obs", json={"filename": "one.mp4"})
    assert resp.status_code == 200
    j = resp.json()
    assert j["success"] is True
    assert j["filename"] == "one.mp4"
    # ensure play_request set on stub
    assert container.obs_widget._play_request is not None

    # play-in-obs by url
    resp2 = client.post("/api/play-in-obs", json={"url": "/videos/two.mp4"})
    assert resp2.status_code == 200
    j2 = resp2.json()
    assert j2["success"] is True
    assert j2["filename"] == "two.mp4"

    # delete existing file
    resp3 = client.delete("/api/delete-video/one.mp4")
    assert resp3.status_code == 200
    assert resp3.json()["success"] is True
    # deleting again should return 404
    resp4 = client.delete("/api/delete-video/one.mp4")
    assert resp4.status_code == 404

    # invalid filename (path traversal) must be rejected
    resp_bad = client.post("/api/play-in-obs", json={"filename": "../secret.mp4"})
    assert resp_bad.status_code == 400
    assert resp_bad.json()["success"] is False
