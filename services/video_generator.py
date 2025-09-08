"""
Video generation service using AIML API Veo3.
Creates celebration videos for qualifying donations.
"""

import logging
import json
import time
import os
import requests
from typing import Optional, Dict, Any
from services.aiml_client import AIMLClient

class VideoGenerator:
    """Service for generating celebration videos using AIML API Veo3."""
    
    def __init__(self, config):
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # AIML API settings
        self.base_url = "https://api.aimlapi.com/v2"
        self.api_key = os.getenv('AIMLAPI_KEY')
        
        if not self.api_key:
            self.logger.warning("AIMLAPI_KEY not found - video generation will not work")
        
        # Video generation settings
        self.latest_video_path = None
        self.generation_count = 0
        self.client = AIMLClient(api_key=self.api_key, logger=self.logger)
        self.system_prompt = ""  # Initialize system prompt field
        self.active_generation = {"active": False, "status": "idle"}
        
        # No automatic retries - each generation requires manual approval
        self.logger.info("VideoGenerator initialized with AIML API (no automatic retries)")
    
    def _check_api_key(self):
        """Check if AIML API key is available."""
        if not self.client.has_api_key():
            self.logger.error("AIMLAPI_KEY is required for video generation")
            return False
        return True
    
    def generate_video(
        self,
        donation_info: Dict[str, Any],
        amount_rub: float,
        custom_prompt: Optional[str] = None,
        resolution: Optional[str] = None,
        duration: Optional[int] = None,
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        enhance_prompt: Optional[bool] = True,
        generate_audio: Optional[bool] = True,
    ) -> Optional[str]:
        """Generate celebration video for donation using AIML API (no automatic retries).

        Optional parameters (passed to AIML API):
        - resolution: "720P" or "1080P"
        - duration: seconds (int)
        - negative_prompt: string
        - seed: int
        - enhance_prompt: bool
        - generate_audio: bool
        """
        try:
            if not self._check_api_key():
                return None
            
            self.generation_count += 1
            video_filename = f"celebration_{int(time.time())}_{self.generation_count}.mp4"
            video_path = os.path.join(self.config.videos_directory, video_filename)
            
            self.logger.info(f"Generating video for {amount_rub:.2f} RUB donation from {donation_info['username']}")
            
            # Track active generation state for UI/progress
            try:
                self.active_generation = {
                    "active": True,
                    "status": "starting",
                    "started_at": time.time(),
                    "donation": {
                        "username": donation_info.get("username"),
                        "message": donation_info.get("message", ""),
                    },
                    "amount_rub": amount_rub,
                }
            except Exception:
                pass
            
            # Use custom prompt if provided, otherwise build from donation message by default
            donation_message = str(donation_info.get('message') or '').strip()
            if custom_prompt:
                base_prompt = custom_prompt
                self.logger.info(f"Using custom prompt: {base_prompt[:100]}...")
            else:
                if donation_message:
                    base_prompt = donation_message
                    self.logger.info(f"Using donation message as base prompt: {base_prompt[:100]}...")
                else:
                    base_prompt = self.config.get_video_prompt(amount_rub)
                    self.logger.info(f"Using amount-based fallback prompt: {base_prompt[:100]}...")
            
            # Prepend system prompt ("Custom Video Prompt") if available
            if self.system_prompt.strip():
                prompt = f"{self.system_prompt.strip()}\n\n{base_prompt}"
                self.logger.info(f"System prompt applied: {self.system_prompt[:50]}...")
            else:
                prompt = base_prompt
            
            # Start video generation task
            generation_id = self._start_video_generation(
                prompt,
                resolution=resolution,
                duration=duration,
                negative_prompt=negative_prompt,
                seed=seed,
                enhance_prompt=enhance_prompt,
                generate_audio=generate_audio,
            )
            if not generation_id:
                try:
                    self.active_generation = {"active": False, "status": "error", "error": "start_failed"}
                except Exception:
                    pass
                return None
            # Store generation id and initial queued status
            try:
                self.active_generation["generation_id"] = generation_id
                # status will be updated by progress callback, but set a sensible default
                if self.active_generation.get("status") == "starting":
                    self.active_generation["status"] = "queued"
            except Exception:
                pass
            
            # Wait for completion and get result
            video_url = self._wait_for_completion(generation_id, progress_callback=self._on_progress)
            if not video_url:
                try:
                    # Preserve active flag only if still running; otherwise mark as error
                    self.active_generation.update({"active": False, "status": "error"})
                except Exception:
                    pass
                return None
            
            # Download video
            try:
                self.active_generation["status"] = "downloading"
            except Exception:
                pass
            if self._download_video(video_url, video_path):
                self.latest_video_path = video_path
                try:
                    self.active_generation.update({
                        "active": False,
                        "status": "done",
                        "finished_at": time.time(),
                        "video_path": video_path
                    })
                except Exception:
                    pass
                self.logger.info(f"Video successfully generated and saved: {video_path}")
                return video_path
            else:
                try:
                    self.active_generation.update({"active": False, "status": "error", "error": "download_failed"})
                except Exception:
                    pass
                return None
                
        except Exception as e:
            self.logger.error(f"Error generating AIML Veo3 video: {e}", exc_info=True)
            return None
    
    def _start_video_generation(
        self,
        prompt: str,
        resolution: Optional[str] = None,
        duration: Optional[int] = None,
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        enhance_prompt: Optional[bool] = True,
        generate_audio: Optional[bool] = True,
    ) -> Optional[str]:
        """Start video generation task and return generation ID (delegates to AIMLClient).

        Attempts to call AIMLClient.start_generation with extended keyword arguments
        when supported; falls back to the simple signature (prompt only) for
        older/stub clients used in tests.
        """
        try:
            # Prefer calling the extended signature (if AIMLClient supports it)
            return self.client.start_generation(
                prompt=prompt,
                resolution=resolution,
                duration=duration,
                negative_prompt=negative_prompt,
                seed=seed,
                enhance_prompt=enhance_prompt,
                generate_audio=generate_audio,
            )
        except TypeError:
            # Fallback for older/stub clients that accept only (prompt)
            try:
                return self.client.start_generation(prompt)
            except Exception as e:
                self.logger.error(f"Error starting AIML video generation (fallback): {e}")
                return None
        except Exception as e:
            self.logger.error(f"Error starting AIML video generation: {e}")
            return None
    

    
    def _wait_for_completion(self, generation_id: str, progress_callback: Optional[Any] = None) -> Optional[str]:
        """Wait for AIML video generation to complete and return video URL (delegates to AIMLClient)."""
        try:
            return self.client.wait_for_completion(generation_id, progress_callback=progress_callback)
        except Exception as e:
            self.logger.error(f"Error waiting for AIML completion: {e}")
            try:
                self.active_generation.update({"active": False, "status": "error", "error": str(e)})
            except Exception:
                pass
            return None
    
    def _download_video(self, video_url: str, local_path: str) -> bool:
        """Download video from AIML URL to local path (delegates to AIMLClient)."""
        try:
            return self.client.download_video(video_url, local_path)
        except Exception as e:
            self.logger.error(f"Error downloading video: {e}")
            return False
    
    def _on_progress(self, info: Dict[str, Any]) -> None:
        """Internal progress callback to update active generation state."""
        try:
            if not isinstance(self.active_generation, dict):
                self.active_generation = {}
            # Merge relevant fields
            status = info.get("status") or info.get("phase") or "running"
            self.active_generation.update({
                "status": status,
                "elapsed": info.get("elapsed", self.active_generation.get("elapsed")),
            })
            if info.get("video_url"):
                self.active_generation["video_url"] = info["video_url"]
        except Exception:
            pass

    def get_generation_status(self) -> Dict[str, Any]:
        """Return current/last generation status with derived progress indicator."""
        try:
            from copy import deepcopy
            state = deepcopy(self.active_generation) if isinstance(self.active_generation, dict) else {}
        except Exception:
            state = dict(self.active_generation or {})
        status = (state.get("status") or "idle").lower()
        # Map statuses to rough progress percentages
        mapping = {
            "idle": 0,
            "starting": 5,
            "queued": 10,
            "waiting": 15,
            "active": 30,
            "generating": 70,
            "completed": 85,
            "downloading": 90,
            "done": 100,
            "timeout": 100,
            "error": 100,
        }
        state["progress"] = mapping.get(status, 50)
        state["active"] = bool(state.get("active", False))
        return state

    def get_latest_video_path(self) -> Optional[str]:
        """Get path to the latest generated video."""
        return self.latest_video_path
    

    
    def list_generated_videos(self) -> list:
        """List all generated videos."""
        try:
            videos = []
            if os.path.exists(self.config.videos_directory):
                for filename in os.listdir(self.config.videos_directory):
                    if filename.endswith('.mp4'):
                        full_path = os.path.join(self.config.videos_directory, filename)
                        videos.append({
                            'filename': filename,
                            'path': full_path,
                            'size': os.path.getsize(full_path),
                            'created': os.path.getctime(full_path)
                        })
            
            # Sort by creation time, newest first
            videos.sort(key=lambda x: x['created'], reverse=True)
            return videos
            
        except Exception as e:
            self.logger.error(f"Error listing videos: {e}")
            return []
