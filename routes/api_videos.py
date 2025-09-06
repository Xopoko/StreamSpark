#!/usr/bin/env python3
"""
Video-related API routes:

- Recent videos: GET /api/recent-videos
- All videos:    GET /api/all-videos
- Delete video:  DELETE /api/delete-video/{filename}
- Play in OBS:   POST /api/play-in-obs
"""

import os
import time
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from core.state import get_container
from utils.files import is_safe_video_filename

router = APIRouter(prefix="/api", tags=["videos"])
logger = logging.getLogger(__name__)


@router.get("/recent-videos")
def get_recent_videos() -> JSONResponse:
    try:
        container = get_container()
        videos: List[Dict[str, Any]] = []
        for item in container.obs_widget.list_videos()[:5]:
            videos.append(
                {
                    "filename": item["filename"],
                    "mtime": item["created"],
                    "url": f"/videos/{item['filename']}",
                }
            )

        return JSONResponse(content={"success": True, "videos": videos})
    except Exception as e:
        logger.error(f"Error fetching recent videos: {e}")
        return JSONResponse(content={"success": False, "videos": []})


@router.get("/all-videos")
def get_all_videos() -> JSONResponse:
    try:
        container = get_container()
        videos: List[Dict[str, Any]] = []
        for item in container.obs_widget.list_videos():
            videos.append(
                {
                    "filename": item["filename"],
                    "url": f"/videos/{item['filename']}",
                    "created": item["created"],
                    "size": item["size"],
                }
            )
        return JSONResponse(content={"success": True, "videos": videos})
    except Exception as e:
        logger.error(f"Error fetching all videos: {e}")
        return JSONResponse(content={"success": False, "videos": []})


@router.delete("/delete-video/{filename}")
def delete_video(filename: str) -> JSONResponse:
    try:
        container = get_container()
        if not is_safe_video_filename(filename):
            return JSONResponse(content={"success": False, "error": "Invalid filename"}, status_code=400)

        video_path = os.path.join(container.config.videos_directory, filename)
        if not os.path.exists(video_path):
            return JSONResponse(content={"success": False, "error": "Video not found"}, status_code=404)

        os.remove(video_path)
        logger.info(f"Video deleted: {filename}")
        return JSONResponse(content={"success": True, "message": "Video deleted successfully"})
    except Exception as e:
        logger.error(f"Error deleting video {filename}: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)


@router.post("/play-in-obs")
def play_in_obs(payload: Dict[str, Any] = Body(...)) -> JSONResponse:
    """
    Queue a specific generated video to be played in the OBS widget.
    Accepts either {"filename": "name.mp4"} or {"url": "/videos/name.mp4"}.
    """
    try:
        container = get_container()
        filename = (payload.get("filename") or "").strip()
        url = (payload.get("url") or "").strip()

        # If only URL is provided, try to extract filename (supports /videos/<filename>.mp4[?query])
        if not filename and url:
            try:
                clean = url.split("#")[0].split("?")[0]
                filename = clean.rsplit("/", 1)[-1]
            except Exception:
                filename = ""

        if not filename or not is_safe_video_filename(filename):
            return JSONResponse(content={"success": False, "error": "Invalid filename"}, status_code=400)

        # Ensure file exists and is resolvable
        abs_path = container.obs_widget.resolve_video_path(filename)
        if not abs_path:
            return JSONResponse(content={"success": False, "error": "Video not found"}, status_code=404)

        # Set one-shot play request; the widget will consume it on next poll
        container.obs_widget._play_request = {"filename": filename, "ts": int(time.time())}
        logger.info(f"Queued video to play in OBS: {filename}")

        return JSONResponse(content={"success": True, "message": "Play request queued", "filename": filename})
    except Exception as e:
        logger.error(f"Error queuing play request: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)
