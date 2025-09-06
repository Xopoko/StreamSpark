#!/usr/bin/env python3
"""
Generation-related API routes:

- System prompt:   GET/POST /api/system-prompt
- Custom generate: POST /api/generate-video
- Veo generate:    POST /api/generate-veo-video
"""

import os
import threading
import logging
import time
from typing import Any, Dict

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from core.state import get_container

router = APIRouter(prefix="/api", tags=["generation"])
logger = logging.getLogger(__name__)

@router.get("/generation-status")
def generation_status() -> JSONResponse:
    try:
        container = get_container()
        status = container.video_generator.get_generation_status()
        return JSONResponse(content={"success": True, "status": status})
    except Exception as e:
        logger.error(f"Error getting generation status: {e}")
        return JSONResponse(content={"success": False, "error": str(e)})


@router.get("/system-prompt")
def get_system_prompt() -> JSONResponse:
    try:
        container = get_container()
        prompt = getattr(
            container.video_generator,
            "system_prompt",
            "Create a celebratory video for a donation. Make it engaging and thankful.",
        )
        return JSONResponse(content={"success": True, "prompt": str(prompt)})
    except Exception as e:
        logger.error(f"Error getting system prompt: {e}")
        return JSONResponse(content={"success": False, "error": str(e)})


@router.post("/system-prompt")
def set_system_prompt(payload: Dict[str, Any] = Body(...)) -> JSONResponse:
    try:
        prompt = (payload.get("prompt") or payload.get("custom_prompt") or "").strip()
        if not prompt:
            return JSONResponse(content={"success": False, "error": "System prompt cannot be empty"})

        container = get_container()
        # Apply in-memory to the running video generator
        container.video_generator.system_prompt = prompt
        logger.info("System prompt updated successfully (in-memory)")
        return JSONResponse(content={"success": True, "message": "System prompt saved successfully"})
    except Exception as e:
        logger.error(f"Error setting system prompt: {e}")
        return JSONResponse(content={"success": False, "error": str(e)})


@router.post("/generate-video")
def generate_custom_video(payload: Dict[str, Any] = Body(...)) -> JSONResponse:
    try:
        prompt = (payload.get("prompt") or payload.get("custom_prompt") or "").strip()
        if not prompt:
            return JSONResponse(content={"success": False, "error": "Prompt is required"}, status_code=400)

        container = get_container()

        def _run() -> None:
            try:
                logger.info(f"Generating custom video with prompt: {prompt[:100]}...")
                donation_info = {
                    "username": "Custom",
                    "message": f"Custom prompt: {prompt[:30]}...",
                    "currency": "RUB",
                }
                video_path = container.video_generator.generate_video(
                    donation_info=donation_info,
                    amount_rub=1000,
                    custom_prompt=prompt,
                )
                if video_path:
                    logger.info(f"Custom video generated successfully: {video_path}")
                else:
                    logger.error("Failed to generate custom video")
            except Exception as e:
                logger.error(f"Error generating custom video: {e}")

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return JSONResponse(content={"success": True, "message": "Video generation started"})
    except Exception as e:
        logger.error(f"Error in custom video generation endpoint: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)


@router.post("/generate-veo-video")
def generate_veo_video(payload: Dict[str, Any] = Body(...)) -> JSONResponse:
    try:
        prompt = (payload.get("prompt") or "").strip()
        duration = payload.get("duration", "5s")
        quality = payload.get("quality", "preview")

        if not prompt:
            return JSONResponse(content={"success": False, "error": "Prompt cannot be empty"}, status_code=400)

        logger.info(f"Generating Veo video - Prompt: {prompt[:50]}..., Duration: {duration}, Quality: {quality}")
        container = get_container()
        donation_info = {
            "username": "Test User",
            "message": f"Testing Veo generation: {prompt[:30]}...",
            "currency": "RUB",
        }
        video_path = container.video_generator.generate_video(
            donation_info=donation_info,
            amount_rub=1000,
            custom_prompt=prompt,
        )
        if video_path and os.path.exists(video_path):
            video_filename = os.path.basename(video_path)
            video_url = f"/videos/{video_filename}"
            logger.info(f"Veo video generated successfully: {video_filename}")
            return JSONResponse(content={"success": True, "video_url": video_url, "message": "Video generated successfully"})
        else:
            logger.error("Failed to generate Veo video")
            return JSONResponse(
                content={
                    "success": False,
                    "error": "Video generation failed. Please check your API key and try again.",
                    "rate_limited": False,
                },
                status_code=500,
            )
    except Exception as e:
        logger.error(f"Error in Veo video generation endpoint: {e}")
        return JSONResponse(content={"success": False, "error": f"Server error: {str(e)}"}, status_code=500)
