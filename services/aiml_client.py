"""AIML API client for Veo3 video generation.

Encapsulates HTTP interactions:
- start_generation(prompt) -> generation_id
- wait_for_completion(generation_id) -> video_url
- download_video(video_url, local_path) -> bool
"""

import json
import logging
import os
import time
from typing import Optional, Dict, Any

import requests


class AIMLClient:
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.aimlapi.com/v2", logger: Optional[logging.Logger] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.getenv("AIMLAPI_KEY")
        self.logger = logger or logging.getLogger(__name__)

    def has_api_key(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def start_generation(self, prompt: str) -> Optional[str]:
        """Start video generation task and return generation ID."""
        try:
            url = f"{self.base_url}/generate/video/google/generation"
            data = {
                "model": "google/veo3",
                "prompt": prompt,
            }

            self.logger.info("Starting AIML Veo3 video generation")
            self.logger.debug(f"Request data: {json.dumps(data, indent=2)}")

            response = requests.post(url, json=data, headers=self._headers(), timeout=30)

            if response.status_code >= 400:
                self.logger.error(f"AIML API Error: {response.status_code} - {response.text}")
                return None

            response_data = response.json()
            self.logger.debug(f"API Response: {json.dumps(response_data, indent=2)}")

            generation_id = response_data.get("id")
            if not generation_id:
                self.logger.error("No generation ID in response")
                return None

            self.logger.info(f"AIML Veo3 video generation started, ID: {generation_id}")
            return generation_id

        except Exception as e:
            self.logger.error(f"Error starting AIML video generation: {e}")
            return None

    def wait_for_completion(self, generation_id: str, max_wait_time: float = 1000.0, poll_interval: float = 10.0, progress_callback: Optional[Any] = None) -> Optional[str]:
        """Wait for AIML video generation to complete and return video URL."""
        try:
            start_time = time.time()
            self.logger.info(f"Waiting for AIML Veo3 video generation to complete: {generation_id}")

            url = f"{self.base_url}/generate/video/google/generation"

            while time.time() - start_time < max_wait_time:
                elapsed = int(time.time() - start_time)
                self.logger.info(f"Polling AIML video status (elapsed: {elapsed}s)")

                params = {"generation_id": generation_id}
                response = requests.get(url, params=params, headers=self._headers(), timeout=30)

                if response.status_code >= 400:
                    self.logger.error(f"Error polling status: {response.status_code} - {response.text}")
                    return None

                response_data = response.json()
                status = response_data.get("status")
                self.logger.info(f"Status: {status}")
                # Progress callback on each poll
                if progress_callback:
                    try:
                        progress_callback({"phase": "poll", "status": status, "elapsed": elapsed})
                    except Exception:
                        pass

                if status in ["waiting", "active", "queued", "generating"]:
                    self.logger.info(f"Still waiting... Checking again in {poll_interval} seconds.")
                    time.sleep(poll_interval)
                elif status == "completed":
                    self.logger.info("AIML video generation completed!")
                    video_info = response_data.get("video", {})
                    video_url = video_info.get("url")

                    if video_url:
                        self.logger.info(f"Video URL: {video_url}")
                        if progress_callback:
                            try:
                                progress_callback({"phase": "completed", "status": "completed", "video_url": video_url, "elapsed": elapsed})
                            except Exception:
                                pass
                        return video_url
                    else:
                        self.logger.error("No video URL in completed response")
                        if progress_callback:
                            try:
                                progress_callback({"phase": "completed", "status": "error", "error": "no_video_url", "elapsed": elapsed})
                            except Exception:
                                pass
                        return None
                else:
                    self.logger.error(f"Video generation failed with status: {status}")
                    if progress_callback:
                        try:
                            progress_callback({"phase": "error", "status": status, "elapsed": elapsed})
                        except Exception:
                            pass
                    return None

            self.logger.error(f"AIML video generation timed out after {max_wait_time} seconds")
            if progress_callback:
                try:
                    progress_callback({"phase": "timeout", "status": "timeout"})
                except Exception:
                    pass
            return None

        except Exception as e:
            self.logger.error(f"Error waiting for AIML completion: {e}")
            if progress_callback:
                try:
                    progress_callback({"phase": "error", "status": "error", "error": str(e)})
                except Exception:
                    pass
            return None

    def download_video(self, video_url: str, local_path: str) -> bool:
        """Download video from AIML URL to local path."""
        try:
            self.logger.info(f"Downloading video from: {video_url}")

            response = requests.get(video_url, stream=True, timeout=60)
            response.raise_for_status()

            os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            file_size = os.path.getsize(local_path)
            self.logger.info(f"Video downloaded to: {local_path} ({file_size} bytes)")
            return True

        except Exception as e:
            self.logger.error(f"Error downloading video: {e}")
            return False
