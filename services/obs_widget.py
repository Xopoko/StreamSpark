"""
OBS widget service for displaying celebration videos.
Provides helpers for OBS browser source integration (framework-agnostic).
"""

import logging
import os
import time
from datetime import datetime
from typing import List, Dict, Optional, TypedDict
from utils.files import is_safe_video_filename

class PlayRequest(TypedDict):
    filename: str
    ts: int


class OBSWidget:
    """Service for OBS browser widget functionality."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.videos_directory = "generated_videos"
        self._play_request: Optional[PlayRequest] = None
        self.logger.info("OBSWidget initialized")

    def template_name(self) -> str:
        """Return the template name for rendering the widget page."""
        return "widget.html"

    def get_latest_video_data(self) -> Dict:
        """Get information about the latest generated video."""
        try:
            # If there is an explicit play request, serve it first (one-shot)
            try:
                req = getattr(self, "_play_request", None)
            except Exception:
                req = None

            if req:
                # Serve requested video for a short TTL window to allow multiple clients to pick it up
                ttl_seconds = 8
                try:
                    req_ts = int(req.get("ts") or 0)
                except Exception:
                    req_ts = 0

                if req_ts and (time.time() - req_ts) > ttl_seconds:
                    # Expired request; clear and fall back to latest
                    self._play_request = None
                else:
                    filename = req.get("filename")
                    if filename and self._is_safe_filename(filename):
                        video_path = os.path.join(self.videos_directory, filename)
                        if os.path.exists(video_path):
                            try:
                                created_ts = os.path.getctime(video_path)
                                size = os.path.getsize(video_path)
                            except OSError:
                                created_ts = datetime.now().timestamp()
                                size = 0

                            # Do not clear _play_request here; let it expire by TTL
                            return {
                                "status": "success",
                                "requested": True,
                                "request_id": req_ts,
                                "video": {
                                    "filename": filename,
                                    "url": f"/videos/{filename}",
                                    "created": datetime.fromtimestamp(created_ts).isoformat(),
                                    "size": size,
                                },
                                "total_videos": len(self._list_videos()),
                            }

            videos = self._list_videos()

            if not videos:
                return {
                    "status": "no_videos",
                    "message": "No videos available",
                    "video": None,
                }

            latest_video = videos[0]  # Already sorted by newest first

            return {
                "status": "success",
                "requested": False,
                "video": {
                    "filename": latest_video["filename"],
                    "url": f"/videos/{latest_video['filename']}",
                    "created": datetime.fromtimestamp(latest_video["created"]).isoformat(),
                    "size": latest_video["size"],
                },
                "total_videos": len(videos),
            }

        except Exception as e:
            self.logger.error(f"Error getting latest video: {e}")
            return {
                "status": "error",
                "message": str(e),
                "video": None,
            }

    def resolve_video_path(self, filename: str) -> Optional[str]:
        """Resolve absolute video file path if safe and exists, else None."""
        try:
            if not self._is_safe_filename(filename):
                self.logger.warning(f"Unsafe filename requested: {filename}")
                return None

            video_path = os.path.join(self.videos_directory, filename)
            if not os.path.exists(video_path):
                self.logger.warning(f"Video file not found: {filename}")
                return None

            return os.path.abspath(video_path)
        except Exception as e:
            self.logger.error(f"Error resolving video path {filename}: {e}")
            return None

    def list_videos(self) -> List[Dict]:
        """Public accessor to list all available videos sorted by creation time."""
        return self._list_videos()

    def _list_videos(self) -> List[Dict]:
        """List all available videos sorted by creation time."""
        try:
            videos: List[Dict] = []

            if not os.path.exists(self.videos_directory):
                return videos

            for filename in os.listdir(self.videos_directory):
                if filename.endswith(".mp4") and self._is_safe_filename(filename):
                    full_path = os.path.join(self.videos_directory, filename)
                    try:
                        videos.append(
                            {
                                "filename": filename,
                                "path": full_path,
                                "size": os.path.getsize(full_path),
                                "created": os.path.getctime(full_path),
                            }
                        )
                    except OSError:
                        # Skip files that can't be accessed
                        continue

            # Sort by creation time, newest first
            videos.sort(key=lambda x: x["created"], reverse=True)
            return videos

        except Exception as e:
            self.logger.error(f"Error listing videos: {e}")
            return []

    def _is_safe_filename(self, filename: str) -> bool:
        """Check if filename is safe to serve."""
        try:
            return is_safe_video_filename(filename)
        except Exception:
            return False

    def get_widget_status(self) -> Dict:
        """Get widget status information."""
        try:
            videos = self._list_videos()

            return {
                "status": "active",
                "total_videos": len(videos),
                "latest_video": videos[0]["filename"] if videos else None,
                "videos_directory": self.videos_directory,
                "widget_url": "/widget",
            }

        except Exception as e:
            self.logger.error(f"Error getting widget status: {e}")
            return {
                "status": "error",
                "error": str(e),
            }
