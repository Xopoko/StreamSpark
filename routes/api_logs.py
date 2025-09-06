#!/usr/bin/env python3
"""
Logs and stats API routes:

- Logs:  GET /api/logs
- Stats: GET /api/stats
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from core.state import get_container
from core.logging_utils import get_recent_logs

router = APIRouter(prefix="/api", tags=["logs"])
logger = logging.getLogger(__name__)


def _parse_access_log(entry: Dict[str, Any], show_ip: bool = False) -> Optional[Dict[str, Any]]:
    """
    Parse uvicorn.access style message:
    Examples:
      '127.0.0.1:61036 - "GET /api/logs?since=... HTTP/1.1" 200'
      '"GET /api/stats HTTP/1.1" 200 OK'
    """
    msg = entry.get("message", "")
    logger_name = entry.get("logger", "")

    data = {
        "id": entry["timestamp"],
        "timestamp": datetime.fromtimestamp(entry["timestamp"] / 1000).strftime("%Y-%m-%dT%H:%M:%S"),
        "timestamp_ms": entry["timestamp"],
        "level": entry.get("level", "INFO"),
        "message": msg,
        "logger": logger_name,
        "type": "general",
    }

    if "uvicorn.access" not in logger_name:
        return data

    try:
        # Find quoted part "METHOD PATH HTTP/1.1"
        first_q = msg.find('"')
        second_q = msg.find('"', first_q + 1) if first_q != -1 else -1
        request_part = ""
        status_part = ""

        if first_q != -1 and second_q != -1:
            request_part = msg[first_q + 1 : second_q]
            status_part = msg[second_q + 1 :].strip()
        else:
            # fallback: sometimes uvicorn logs: 127.0.0.1:port - "GET /path HTTP/1.1" 200
            parts = msg.split('"')
            if len(parts) >= 3:
                request_part = parts[1]
                status_part = parts[2].strip()

        method = ""
        path = ""
        if request_part:
            comps = request_part.split(" ")
            if len(comps) >= 2:
                method = comps[0]
                path = comps[1]

        status = 200
        for token in status_part.split():
            if token.isdigit():
                status = int(token)
                break

        base_path = path.split("?")[0] if path else ""
        ip = ""
        if show_ip:
            # extract IP if present 'IP:port - "GET ...'
            dash_idx = msg.find(" - ")
            if dash_idx != -1:
                ip = msg[:dash_idx].split()[0]

        data.update(
            {
                "type": "http",
                "method": method or "GET",
                "path": path or "/",
                "signature": f"{method or 'GET'} {base_path or '/'}",
                "status": status,
                "ip": ip,
                "latency": "0ms",
                "request_body": "",
                "response_body": "",
            }
        )
    except Exception:
        # leave as general
        pass

    return data


@router.get("/logs")
def get_logs(since: int = Query(0), show_ip: bool = Query(False)) -> JSONResponse:
    try:
        raw = get_recent_logs(since_ms=since)
        recent_logs: List[Dict[str, Any]] = []
        for entry in raw:
            parsed = _parse_access_log(entry, show_ip=show_ip)
            if parsed:
                recent_logs.append(parsed)

        return JSONResponse(
            content={
                "success": True,
                "logs": recent_logs,
                "total_logs": len(raw),
            }
        )
    except Exception as e:
        logger.error(f"Error fetching logs: {e}")
        return JSONResponse(content={"success": False, "logs": [], "total_logs": 0})


@router.get("/stats")
def get_stats() -> JSONResponse:
    try:
        container = get_container()
        video_count = 0
        if hasattr(container.config, "videos_directory"):
            import os

            if os.path.exists(container.config.videos_directory):
                video_count = len([f for f in os.listdir(container.config.videos_directory) if f.endswith(".mp4")])

        poller_stats = container.donation_poller.get_stats()
        stats = {
            "totalVideos": video_count,
            "totalDonations": poller_stats.get("total_donations_processed", 0),
            "totalAmount": f"${0:.2f}",
            "pollingStatus": "Running" if poller_stats.get("is_running") else "Stopped",
            "apiConfigured": poller_stats.get("has_token", False),
            "lastPoll": poller_stats.get("last_poll_time"),
            "apiErrors": poller_stats.get("api_errors", 0),
        }
        return JSONResponse(content=stats)
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return JSONResponse(
            content={
                "totalVideos": 0,
                "totalDonations": 0,
                "totalAmount": "$0.00",
                "pollingStatus": "Error",
                "apiConfigured": False,
            }
        )
