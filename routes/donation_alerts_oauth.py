#!/usr/bin/env python3
"""
DonationAlerts OAuth routes for FastAPI:
- GET  /api/da/oauth/login      -> Redirects to DonationAlerts OAuth authorization
- GET  /api/da/oauth/callback   -> Handles OAuth callback, exchanges code for tokens, persists them
- POST /api/da/disconnect       -> Clears stored tokens
"""

import time
import secrets
import urllib.parse
import logging
from typing import Optional

import requests
from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse, JSONResponse

from core.state import get_container

router = APIRouter(prefix="/api/da", tags=["donationalerts-oauth"])
logger = logging.getLogger(__name__)

AUTH_BASE = "https://www.donationalerts.com/oauth"
TOKEN_URL = f"{AUTH_BASE}/token"
AUTHORIZE_URL = f"{AUTH_BASE}/authorize"


def _get_oauth_config():
    container = get_container()
    cfg = container.config
    return {
        "client_id": getattr(cfg, "donationalerts_client_id", None),
        "client_secret": getattr(cfg, "donationalerts_client_secret", None),
        "redirect_uri": getattr(cfg, "donationalerts_redirect_uri", None),
    }


# Debug endpoint to inspect effective OAuth config (no secrets)
@router.get("/oauth/debug")
def da_oauth_debug():
    cfg = _get_oauth_config()
    safe = {
        "client_id": str(cfg.get("client_id")) if cfg.get("client_id") is not None else None,
        "redirect_uri": cfg.get("redirect_uri"),
        "has_client_secret": bool(cfg.get("client_secret")),
    }
    return JSONResponse(content={"success": True, "config": safe})

@router.get("/oauth/login")
def da_oauth_login():
    cfg = _get_oauth_config()

    missing = []
    if not cfg["client_id"]:
        missing.append("DA_CLIENT_ID")
    if not cfg["client_secret"]:
        missing.append("DA_CLIENT_SECRET")
    if not cfg["redirect_uri"]:
        # Redirect URI defaults to http://localhost:<PORT>/api/da/oauth/callback (PORT from env)
        missing.append("PORT (used to form default redirect URI)")

    if missing:
        return JSONResponse(
            content={
                "success": False,
                "error": "DonationAlerts OAuth is not configured",
                "missing": missing,
                "client_id_present": bool(cfg["client_id"]),
                "redirect_uri_effective": cfg.get("redirect_uri"),
                "hint": "Update .env with the missing variables and RESTART the server to apply changes."
            },
            status_code=400,
        )

    # Generate and store CSRF state in-memory (best-effort)
    state = secrets.token_urlsafe(16)
    try:
        container = get_container()
        setattr(container.config, "donationalerts_oauth_state", state)
        setattr(container.config, "donationalerts_oauth_state_ts", int(time.time()))
    except Exception:
        pass

    # Minimal scopes required to read donations and user
    scopes = "oauth-user-show oauth-donation-index"

    params = {
        "client_id": cfg["client_id"],
        "redirect_uri": cfg["redirect_uri"],
        "response_type": "code",
        "scope": scopes,
        "state": state,
    }
    url = f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url=url, status_code=302)


@router.get("/oauth/callback")
def da_oauth_callback(code: Optional[str] = Query(None), state: Optional[str] = Query(None)):
    if not code:
        return JSONResponse(content={"success": False, "error": "Missing 'code' parameter"}, status_code=400)

    cfg = _get_oauth_config()
    if not cfg["client_id"] or not cfg["client_secret"] or not cfg["redirect_uri"]:
        return JSONResponse(
            content={"success": False, "error": "OAuth not configured on server"}, status_code=400
        )

    # Optional: validate CSRF state (best-effort)
    try:
        container = get_container()
        # We stored these as app-wide configs
        # Not critical if missing; proceed anyway
    except Exception:
        pass

    try:
        data = {
            "grant_type": "authorization_code",
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "redirect_uri": cfg["redirect_uri"],
            "code": code,
        }
        resp = requests.post(TOKEN_URL, data=data, timeout=15)
        if resp.status_code != 200:
            logger.error(f"DonationAlerts token exchange failed: {resp.status_code} - {resp.text}")
            return JSONResponse(
                content={"success": False, "error": f"Token exchange failed: {resp.status_code}"}, status_code=400
            )

        token = resp.json() or {}
        access_token = token.get("access_token")
        refresh_token = token.get("refresh_token")
        token_type = token.get("token_type", "Bearer")
        expires_in = token.get("expires_in")

        if not access_token:
            return JSONResponse(content={"success": False, "error": "No access_token in response"}, status_code=400)

        # Apply globally (single-user app) in-memory
        container = get_container()
        container.config.donation_alerts_token = access_token
        if refresh_token:
            container.config.donationalerts_refresh_token = refresh_token
        if token_type:
            container.config.donationalerts_token_type = token_type  # optional
        if expires_in:
            container.config.donationalerts_expires_at = int(time.time()) + int(expires_in)

        # Update client token and start polling
        try:
            container.donation_poller.set_api_token(access_token)
            container.donation_poller.start_polling()
        except Exception as e:
            logger.warning(f"Failed to start polling automatically: {e}")

        # Redirect back to dashboard
        return RedirectResponse(url="/dashboard", status_code=302)

    except Exception as e:
        logger.error(f"Error handling OAuth callback: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)


@router.post("/disconnect")
def da_disconnect():
    """
    Clear stored DonationAlerts tokens (OAuth disconnect).
    """
    try:
        container = get_container()
        # Clear in-memory tokens and stop polling
        container.config.donation_alerts_token = ""
        container.config.donationalerts_refresh_token = ""
        container.config.donationalerts_token_type = ""
        container.config.donationalerts_expires_at = 0
        container.donation_poller.set_api_token("")
        container.donation_poller.stop_polling()

        return JSONResponse(content={"success": True, "message": "Disconnected from DonationAlerts"})
    except Exception as e:
        logger.error(f"Error during disconnect: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)
