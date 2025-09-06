#!/usr/bin/env python3
"""
Widget page and video-serving routes for FastAPI.

- GET  /widget                 -> widget.html
- GET  /api/latest-video       -> JSON info about latest video
- GET  /videos/{filename}      -> serve generated video safely
"""

import os
import logging
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from core.state import get_container

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="templates")
router = APIRouter(tags=["widget", "videos"])


@router.get("/widget", response_class=HTMLResponse)
def widget_page(request: Request) -> HTMLResponse:
    container = get_container()
    # Render template directly; service is framework-agnostic now
    return templates.TemplateResponse(container.obs_widget.template_name(), {"request": request})


@router.get("/api/latest-video")
def get_latest_video() -> JSONResponse:
    container = get_container()
    data = container.obs_widget.get_latest_video_data()
    return JSONResponse(content=data)


@router.get("/videos/{filename}")
def serve_video(filename: str):
    container = get_container()
    path = container.obs_widget.resolve_video_path(filename)
    if not path:
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(path, media_type="video/mp4", filename=os.path.basename(path))
