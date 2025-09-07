#!/usr/bin/env python3
"""
StreamSpark FastAPI application entrypoint.

- Replaces Flask with FastAPI
- Mounts static files and templates
- Wires modular routers
- Ports key endpoints from the legacy main.py
"""

import os
import logging
import time
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
# Prefer Starlette's middleware (correct ASGI types); fall back to Uvicorn's if unavailable
try:
    from starlette.middleware.proxy_headers import ProxyHeadersMiddleware  # type: ignore[import]
except Exception:
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware  # type: ignore

# Load .env if present
try:
    from dotenv import load_dotenv

    load_dotenv(override=False)
except Exception:
    pass

from core.logging_utils import setup_logging
from core.container import init_container
from core.state import set_container, get_container

# Routers
from routes.pages import router as pages_router
from routes.widget_videos import router as widget_videos_router
from routes.api_logs import router as api_logs_router
from routes.api_videos import router as api_videos_router
from routes.api_settings import router as api_settings_router
from routes.api_generation import router as api_generation_router
from routes.api_polling import router as api_polling_router
from routes.donation_alerts_oauth import router as da_oauth_router


def validate_configuration() -> bool:
    """Validate environment configuration (non-fatal)."""
    logger = logging.getLogger(__name__)
    watched_env_vars = ["AIMLAPI_KEY", "DA_CLIENT_ID", "DA_CLIENT_SECRET"]

    missing_vars = [var for var in watched_env_vars if not os.getenv(var)]
    if missing_vars:
        logger.warning(f"Missing optional environment variables: {missing_vars}. Some features may be limited until configured.")
        print("\nOptional Environment Variables (set to enable features):")
        print("- AIMLAPI_KEY: AIML API key for video generation")
        print("- DA_CLIENT_ID: DonationAlerts OAuth Client ID")
        print("- DA_CLIENT_SECRET: DonationAlerts OAuth Client Secret")
        return True
    return True


def create_app() -> FastAPI:
    """Application factory."""
    setup_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Initialize container and apply startup config
        container = init_container()
        set_container(container)
        # Best-effort config validation (don't crash the ASGI server)
        valid = validate_configuration()
        if not valid:
            logging.getLogger(__name__).warning("Configuration invalid. Some features may not work until fixed.")
        logging.getLogger(__name__).info("StreamSpark FastAPI app started")
        try:
            yield
        finally:
            try:
                container = get_container()
                container.donation_poller.stop_polling()
            except Exception:
                pass
            logging.getLogger(__name__).info("StreamSpark FastAPI app stopped")

    app = FastAPI(
        title="StreamSpark",
        description="Donation Celebration Video Generator - FastAPI",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Respect X-Forwarded-* headers (similar to Flask ProxyFix)
    app.add_middleware(ProxyHeadersMiddleware)  # type: ignore[arg-type]

    # Static files
    app.mount("/static", StaticFiles(directory="static"), name="static")

    # Include routers
    app.include_router(pages_router)
    app.include_router(widget_videos_router)
    app.include_router(api_logs_router)
    app.include_router(api_videos_router)
    app.include_router(api_settings_router)
    app.include_router(api_generation_router)
    app.include_router(api_polling_router)
    app.include_router(da_oauth_router)


    # Ported endpoints from legacy Flask main.py

    @app.api_route("/test-donation", methods=["GET", "POST"])
    async def test_donation(request: Request):
        """
        Test donation endpoint:
        - GET: Redirects to /dashboard (legacy behavior)
        - POST: Processes test donation and optionally generates a video
        """
        logger = logging.getLogger(__name__)
        if request.method == "GET":
            return RedirectResponse(url="/dashboard")

        try:
            data = await request.json()
            if not data:
                return JSONResponse(content={"success": False, "error": "No JSON data provided"})

            container = get_container()

            donation_info: Dict[str, Any] = {
                "id": f"test_{int(time.time())}",
                "username": (data.get("donor_name") or data.get("name", "Test User")),
                "amount": float(data.get("amount", 1000)),
                "currency": (data.get("currency") or "RUB").upper(),
                "message": data.get("message", "Test donation"),
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }

            # Convert amount to RUB if needed
            amount_rub = donation_info["amount"]
            if donation_info["currency"] != "RUB":
                try:
                    converted = container.currency_converter.convert_to_rub(
                        donation_info["amount"], donation_info["currency"]
                    )
                    if converted:
                        amount_rub = converted
                except Exception as e:
                    logger.warning(f"Currency conversion failed: {e}")

            donation_info["amount_rub"] = amount_rub

            # Generate video if requested and above threshold
            generate_video = bool(data.get("generate_video", True))
            threshold = float(getattr(get_container().config, "donation_threshold_rub", 1000))

            if generate_video and amount_rub >= threshold:
                video_path = container.video_generator.generate_video(
                    donation_info,
                    amount_rub,
                    custom_prompt=f"Create a celebration video for {donation_info['username']}'s donation of {amount_rub:.0f} RUB",
                )
                if video_path:
                    return JSONResponse(
                        content={
                            "success": True,
                            "message": "Test donation processed and video generated",
                            "video_path": video_path,
                            "amount_rub": amount_rub,
                        }
                    )
                else:
                    return JSONResponse(
                        content={
                            "success": True,
                            "message": "Test donation processed - video generation pending approval",
                            "amount_rub": amount_rub,
                        }
                    )
            else:
                return JSONResponse(
                    content={
                        "success": True,
                        "message": f"Test donation processed (no video: {'disabled' if not generate_video else 'below threshold'})",
                        "amount_rub": amount_rub,
                    }
                )
        except Exception as e:
            logging.getLogger(__name__).error(f"Error processing test donation: {e}")
            return JSONResponse(content={"success": False, "error": str(e)})

    @app.get("/status")
    def status() -> Dict[str, Any]:
        port = int(os.environ.get("PORT", 5002))
        return {
            "status": "running",
            "webhook_url": f"http://0.0.0.0:{port}/webhook/donationalerts",
            "widget_url": f"http://0.0.0.0:{port}/widget",
            "test_url": f"http://0.0.0.0:{port}/test-donation",
            "services": {
                "currency_converter": "active",
                "video_generator": "active",
                "webhook_handler": "active",
                "obs_widget": "active",
            },
        }

    return app


# ASGI application
app = create_app()


if __name__ == "__main__":
    # Optional local runner
    import uvicorn

    port = int(os.environ.get("PORT", 5002))
    print("\n" + "=" * 60)
    print("🎉 DONATION CELEBRATION APP (FastAPI) STARTED 🎉")
    print("=" * 60)
    print(f"🎬 OBS Widget URL: http://0.0.0.0:{port}/widget")
    print(f"📊 Status URL: http://0.0.0.0:{port}/status")
    print("=" * 60)
    print("\nPress Ctrl+C to stop the application")
    print("=" * 60 + "\n")
    uvicorn.run("main_fastapi:app", host="0.0.0.0", port=port, log_level="info")
