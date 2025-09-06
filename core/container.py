#!/usr/bin/env python3
"""
Application container and dependency wiring for FastAPI.
Initializes Config and service singletons and exposes helpers for routers.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from config import Config
from services.currency_converter import CurrencyConverter
from services.video_generator import VideoGenerator
from services.donation_alerts_poller import DonationAlertsPoller
from services.obs_widget import OBSWidget


@dataclass
class AppContainer:
    config: Config
    currency_converter: CurrencyConverter
    video_generator: VideoGenerator
    donation_poller: DonationAlertsPoller
    obs_widget: OBSWidget


def apply_initial_config(container: AppContainer) -> None:
    """Apply initial in-memory config (no database). Start/stop poller based on token."""
    logger = logging.getLogger(__name__)
    try:
        # Prefer explicit donation_alerts_token; fall back to legacy env-seeded donationalerts_api_token
        token = getattr(container.config, "donation_alerts_token", "") or getattr(
            container.config, "donationalerts_api_token", ""
        )
        if token:
            container.config.donation_alerts_token = str(token)
            container.donation_poller.set_api_token(container.config.donation_alerts_token)
            try:
                container.donation_poller.start_polling()
            except Exception as e:
                logger.warning(f"Failed to start polling at init: {e}")
        else:
            try:
                container.donation_poller.stop_polling()
            except Exception:
                pass

        logger.info("Initial configuration applied (in-memory)")
    except Exception as e:
        logger.error(f"Error applying initial config: {e}")




def init_container() -> AppContainer:
    """Initialize and wire the application services."""
    logger = logging.getLogger(__name__)
    cfg = Config()

    currency_converter = CurrencyConverter()
    video_generator = VideoGenerator(cfg)
    donation_poller = DonationAlertsPoller(cfg, currency_converter, video_generator)
    obs_widget = OBSWidget()

    # Stop polling by default until token is configured
    donation_poller.stop_polling()

    container = AppContainer(
        config=cfg,
        currency_converter=currency_converter,
        video_generator=video_generator,
        donation_poller=donation_poller,
        obs_widget=obs_widget,
    )

    # Apply in-memory/env-backed config and update services
    apply_initial_config(container)

    logger.info("App container initialized")
    return container
