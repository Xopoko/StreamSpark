#!/usr/bin/env python3
"""
DonationAlerts polling API routes:

- Donations placeholder: GET /api/donations
- Test connection:       GET /api/test-donation-alerts
- Start polling:         POST /api/start-polling
- Stop polling:          POST /api/stop-polling
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter
from fastapi import Body
from fastapi.responses import JSONResponse

from core.state import get_container

router = APIRouter(prefix="/api", tags=["polling"])
logger = logging.getLogger(__name__)


@router.get("/donations")
def get_donations(limit: int = 50) -> JSONResponse:
    try:
        container = get_container()
        # Pull recent donations from the running poller
        recents = container.donation_poller.get_recent_donations(limit=limit)

        # Transform to UI-friendly shape (matching templates/components/dashboard/donations.html)
        donations = []
        for d in recents:
            donations.append({
                "id": d.get("id"),
                "donor": d.get("username") or "Anonymous",
                "amount": d.get("amount") or 0,
                "currency": d.get("currency") or "RUB",
                "message": d.get("message") or "",
                "time": d.get("created_at") or "",
                "isTest": False
            })

        return JSONResponse(content={"success": True, "donations": donations})
    except Exception as e:
        logger.error(f"Error getting recent donations: {e}")
        return JSONResponse(content={"success": False, "donations": [], "error": str(e)})


@router.get("/test-donation-alerts")
def test_donation_alerts() -> JSONResponse:
    try:
        container = get_container()
        result = container.donation_poller.test_api_connection()
        if result.get("success"):
            container.donation_poller.start_polling()
            result["message"] = "Connection successful - polling started"
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error testing DonationAlerts API: {e}")
        return JSONResponse(content={"success": False, "error": str(e)})


@router.post("/start-polling")
def start_polling() -> JSONResponse:
    try:
        container = get_container()
        if not getattr(container.config, "donation_alerts_token", ""):
            return JSONResponse(content={"success": False, "error": "No API token configured"})
        container.donation_poller.start_polling()
        return JSONResponse(content={"success": True, "message": "Polling started"})
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)})


@router.post("/stop-polling")
def stop_polling() -> JSONResponse:
    try:
        container = get_container()
        container.donation_poller.stop_polling()
        return JSONResponse(content={"success": True, "message": "Polling stopped"})
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)})
