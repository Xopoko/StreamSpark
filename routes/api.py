#!/usr/bin/env python3
"""
DEPRECATED: Legacy API router aggregator.

This module is kept for backward compatibility. It aggregates the new, modular
routers under a single `router` so any existing imports like:

    from routes.api import router

continue to work without code changes.

New modular routers:
- routes/api_logs.py
- routes/api_videos.py
- routes/api_settings.py
- routes/api_generation.py
- routes/api_polling.py
"""

from fastapi import APIRouter

# Import new modular routers
from routes.api_logs import router as api_logs_router
from routes.api_videos import router as api_videos_router
from routes.api_settings import router as api_settings_router
from routes.api_generation import router as api_generation_router
from routes.api_polling import router as api_polling_router

# Aggregate into a single router for compatibility
router = APIRouter(prefix="/api")
router.include_router(api_logs_router)
router.include_router(api_videos_router)
router.include_router(api_settings_router)
router.include_router(api_generation_router)
router.include_router(api_polling_router)
