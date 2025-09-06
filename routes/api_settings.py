#!/usr/bin/env python3
"""
Settings and configuration API routes:

- Settings:           GET /api/settings
- DonationAlerts key: POST /api/donation-alerts-token
- Access token:       GET/POST /api/access-token
- Threshold:          GET/POST /api/threshold
- Connection status:  GET /api/connection-status
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from core.state import get_container

router = APIRouter(prefix="/api", tags=["settings"])
logger = logging.getLogger(__name__)


@router.get("/settings")
def get_settings() -> JSONResponse:
    try:
        container = get_container()
        return JSONResponse(
            content={
                "success": True,
                "donation_alerts_token": getattr(container.config, "donation_alerts_token", ""),
                "threshold_amount": getattr(container.config, "donation_threshold_amount", 1000),
                "threshold_currency": getattr(container.config, "donation_threshold_currency", "RUB"),
            }
        )
    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        return JSONResponse(content={"success": False, "error": str(e)})


@router.post("/donation-alerts-token")
def set_donation_alerts_token(payload: Dict[str, Any] = Body(...)) -> JSONResponse:
    try:
        container = get_container()
        token = payload.get("token") or ""
        container.config.donation_alerts_token = token
        container.donation_poller.set_api_token(token)
        # Auto start/stop poller based on token presence
        try:
            if token.strip():
                container.donation_poller.start_polling()
                msg = "DonationAlerts API token saved, polling started"
            else:
                container.donation_poller.stop_polling()
                msg = "DonationAlerts API token cleared, polling stopped"
        except Exception as _e:
            logger.warning(f"Failed to toggle polling after token update: {_e}")
            msg = "DonationAlerts API token saved"
        logger.info("DonationAlerts API token updated")
        return JSONResponse(content={"success": True, "message": msg})
    except Exception as e:
        logger.error(f"Error setting DonationAlerts token: {e}")
        return JSONResponse(content={"success": False, "error": str(e)})


@router.get("/connection-status")
def connection_status() -> JSONResponse:
    try:
        container = get_container()
        has_token = bool(getattr(container.config, "donation_alerts_token", ""))
        return JSONResponse(
            content={
                "configured": True,
                "connected": has_token,
                "message": "Ready for connection" if has_token else "Token not configured",
            }
        )
    except Exception as e:
        logger.error(f"Error getting connection status: {e}")
        return JSONResponse(content={"configured": False, "connected": False, "error": str(e)})


@router.get("/threshold")
def get_threshold() -> JSONResponse:
    container = get_container()
    return JSONResponse(content={"threshold": float(getattr(container.config, "donation_threshold_rub", 1000.0))})


@router.post("/threshold")
def set_threshold(payload: Dict[str, Any] = Body(...)) -> JSONResponse:
    try:
        container = get_container()
        amount = payload.get("threshold")
        currency = "RUB"
        if amount is None:
            amount = payload.get("amount", 1000.0)
            currency = (payload.get("currency") or "RUB").upper()
        amount = float(amount)
        if amount < 0:
            return JSONResponse(content={"success": False, "error": "Threshold must be positive"})

        threshold_rub = amount
        if currency != "RUB":
            converted = container.currency_converter.convert_to_rub(amount, currency)
            if converted is None:
                return JSONResponse(content={"success": False, "error": f"Failed to convert {amount} {currency} to RUB"})
            threshold_rub = float(converted)

        # Apply in-memory
        container.config.donation_threshold_rub = threshold_rub

        logger.info(f"Donation threshold updated to {threshold_rub} RUB (input: {amount} {currency})")
        return JSONResponse(content={"success": True, "message": f"Threshold saved: {threshold_rub} RUB"})
    except Exception as e:
        logger.error(f"Error setting threshold: {e}")
        return JSONResponse(content={"success": False, "error": str(e)})


@router.get("/access-token")
def get_access_token_status() -> JSONResponse:
    container = get_container()
    return JSONResponse(content={"has_token": bool(getattr(container.config, "donation_alerts_token", ""))})


@router.post("/access-token")
def set_access_token(payload: Dict[str, Any] = Body(...)) -> JSONResponse:
    try:
        container = get_container()
        token = (payload.get("access_token") or "").strip()
        container.config.donation_alerts_token = token
        container.donation_poller.set_api_token(token)
        # Auto start/stop poller based on token presence
        try:
            if token:
                container.donation_poller.start_polling()
                msg = "Access token saved, polling started"
            else:
                container.donation_poller.stop_polling()
                msg = "Access token cleared, polling stopped"
        except Exception as _e:
            logger.warning(f"Failed to toggle polling after access token update: {_e}")
            msg = "Access token saved"
        logger.info("Access token updated")
        return JSONResponse(content={"success": True, "message": msg})
    except Exception as e:
        logger.error(f"Error setting access token: {e}")
        return JSONResponse(content={"success": False, "error": str(e)})


@router.get("/aiml-status")
def aiml_status() -> JSONResponse:
    """Diagnostics endpoint to quickly verify AIML and donation processing readiness."""
    try:
        container = get_container()
        vg = container.video_generator
        has_key = False
        try:
            has_key = vg.client.has_api_key() if hasattr(vg, "client") else False
        except Exception:
            has_key = False

        system_prompt = getattr(vg, "system_prompt", "") or ""
        prompt_preview = system_prompt[:120] + ("..." if len(system_prompt) > 120 else "")

        return JSONResponse(
            content={
                "success": True,
                "has_api_key": bool(has_key),
                "threshold_rub": float(getattr(container.config, "donation_threshold_rub", 1000.0)),
                "poller_running": bool(container.donation_poller.is_running),
                "total_donations_processed": container.donation_poller.total_donations_processed,
                "total_videos_generated": container.donation_poller.total_videos_generated,
                "last_poll_time": container.donation_poller.last_poll_time.isoformat()
                if container.donation_poller.last_poll_time
                else None,
                "system_prompt_preview": prompt_preview,
            }
        )
    except Exception as e:
        logger.error(f"Error getting AIML status: {e}")
        return JSONResponse(content={"success": False, "error": str(e)})
