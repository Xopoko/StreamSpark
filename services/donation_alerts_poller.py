"""
DonationAlerts API Polling Service

This service polls the DonationAlerts API for new donations and processes them
according to the configured threshold and video generation settings.
"""

import time
import logging
import requests
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from services.donation_alerts_client import DonationAlertsClient


class DonationAlertsPoller:
    """Polls DonationAlerts API for new donations and processes them."""
    
    def __init__(self, config, currency_converter, video_generator):
        self.config = config
        self.currency_converter = currency_converter
        self.video_generator = video_generator
        self.logger = logging.getLogger(__name__)
        
        # HTTP client
        self.client = DonationAlertsClient(config, logger=self.logger)
        
        # API configuration
        self.api_base = 'https://www.donationalerts.com/api/v1'
        self.oauth_token_url = 'https://www.donationalerts.com/oauth/token'
        self.api_token = None
        
        # Polling state
        self.is_running = False
        self.polling_thread = None
        # (removed last_donation_id per vulture)
        self.processed_donations = set()  # Track processed donation IDs (in-memory only)
        self._processed_order = []  # Maintain insertion order for trimming
        self._processed_lock = threading.Lock()
        # In-memory only; no persistence across restarts
        # Recent donations buffer for UI/history
        self.recent_donations: List[Dict[str, Any]] = []
        self._recent_lock = threading.Lock()
        
        # Rate limiting (60 requests per minute = 1 per second)
        self.min_request_interval = 2.0  # 2 seconds between requests to be safe
        self.last_request_time = 0
        
        # Statistics
        self.total_donations_processed = 0
        self.total_videos_generated = 0
        self.last_poll_time = None
        self.api_errors = 0
        
        self.logger.info("DonationAlerts poller initialized")
    
    def set_api_token(self, token: str):
        """Set the API token for authentication."""
        self.api_token = token
        try:
            self.client.set_api_token(token)
        except Exception:
            pass
        masked = "*" * 8
        try:
            masked = f"*** (len={len(token)})"
        except Exception:
            pass
        self.logger.info(f"API token updated: {masked}")
    
    def start_polling(self):
        """Start the polling service in a background thread."""
        if self.is_running:
            self.logger.warning("Polling is already running")
            return
        
        if not self.api_token:
            self.logger.error("Cannot start polling: API token not configured")
            return
        
        self.is_running = True
        self.polling_thread = threading.Thread(target=self._polling_loop, daemon=True)
        self.polling_thread.start()
        self.logger.info("Started DonationAlerts polling service")
    
    def stop_polling(self):
        """Stop the polling service."""
        self.is_running = False
        if self.polling_thread:
            self.polling_thread.join(timeout=5)
        self.logger.info("Stopped DonationAlerts polling service")
    
    def _polling_loop(self):
        """Main polling loop that runs in a background thread."""
        while self.is_running:
            try:
                # Rate limiting
                time_since_last_request = time.time() - self.last_request_time
                if time_since_last_request < self.min_request_interval:
                    time.sleep(self.min_request_interval - time_since_last_request)
                
                # Fetch new donations
                donations = self._fetch_donations()
                if donations:
                    self._process_donations(donations)
                
                self.last_poll_time = datetime.now()
                
            except Exception as e:
                self.logger.error(f"Error in polling loop: {e}")
                self.api_errors += 1
                time.sleep(5)  # Wait longer on errors
    
    def _fetch_donations(self) -> Optional[List[Dict[str, Any]]]:
        """Fetch donations via the DonationAlerts client."""
        if not self.client.has_token():
            return None
        try:
            self.last_request_time = time.time()
            donations = self.client.fetch_donations(page=1, limit=10)
            if donations is not None:
                self.logger.debug(f"Fetched {len(donations)} donations from API")
            return donations
        except Exception as e:
            self.logger.error(f"Unexpected error fetching donations: {e}")
            return None
    
    def _refresh_access_token(self) -> bool:
        """Delegate token refresh to the DonationAlerts client."""
        try:
            success = self.client.refresh_access_token()
            if success:
                # Sync local copy used by start/stop checks and stats
                self.api_token = self.client.get_api_token()
            return success
        except Exception as e:
            self.logger.error(f"Unexpected error refreshing token: {e}")
            return False



    def _is_test_donation(self, donation: Dict[str, Any]) -> bool:
        """Detect if donation is a test event. Fail-safe to treat ambiguous as test."""
        try:
            for key in ("is_test", "isTest", "test", "testing"):
                if key in donation and bool(donation.get(key)):
                    return True
            alert_type = donation.get("alert_type") or donation.get("type")
            if isinstance(alert_type, str) and alert_type.lower() == "test":
                return True
            return False
        except Exception:
            return True  # Fail-safe: treat unknown as test to avoid unintended spend

    def _parse_created_at(self, created_at_val: Any) -> Optional[datetime]:
        """Parse created_at into datetime, supporting multiple common formats."""
        try:
            if not created_at_val:
                return None
            if isinstance(created_at_val, datetime):
                return created_at_val
            s = str(created_at_val).strip()
            # Try ISO formats first
            try:
                if s.endswith("Z"):
                    return datetime.fromisoformat(s.replace("Z", "+00:00"))
                return datetime.fromisoformat(s)
            except Exception:
                pass
            # Try common patterns
            fmts = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%f%z",
            ]
            for fmt in fmts:
                try:
                    return datetime.strptime(s, fmt)
                except Exception:
                    continue
            return None
        except Exception:
            return None

    def _is_fresh(self, created_dt: Optional[datetime], window_minutes: int = 5) -> bool:
        """Return True if created_dt within last window_minutes."""
        if not created_dt:
            return False
        try:
            now = datetime.now(created_dt.tzinfo) if getattr(created_dt, "tzinfo", None) else datetime.now()
            return (now - created_dt) <= timedelta(minutes=window_minutes)
        except Exception:
            return False

    def _process_donations(self, donations: List[Dict[str, Any]]):
        """Process new donations and trigger video generation if needed."""
        for donation in donations or []:
            donation_id = donation.get("id")
            # Skip if already processed
            if donation_id in self.processed_donations:
                continue
            # Defer marking as processed to _process_single_donation based on rules
            self._process_single_donation(donation)
    
    def _process_single_donation(self, donation: Dict[str, Any]):
        """Process a single donation and check if it qualifies for video generation.

        Rules:
        - Only real (non-test) donations.
        - Only if donation is not older than 5 minutes.
        - Idempotent across restarts by persisting processed donation IDs.
        """
        try:
            donation_id = donation.get('id')
            if not donation_id:
                return

            # Skip if already processed
            if donation_id in self.processed_donations:
                return

            # Record for UI/history (non-blocking)
            try:
                self._record_recent(donation)
            except Exception:
                pass

            # Filter out test donations
            if self._is_test_donation(donation):
                self.logger.info(f"Skipping test donation {donation_id}")
                with self._processed_lock:
                    self.processed_donations.add(donation_id)
                    self._processed_order.append(donation_id)
                    if len(self._processed_order) > 2000:
                        to_trim = len(self._processed_order) - 2000
                        for _ in range(to_trim):
                            old = self._processed_order.pop(0)
                            try:
                                self.processed_donations.remove(old)
                            except KeyError:
                                pass
                    # In-memory only; no persistence
                return

            # Freshness check (<= 5 minutes)
            created_at = donation.get('created_at', '')
            created_dt = self._parse_created_at(created_at)
            if not self._is_fresh(created_dt, window_minutes=5):
                self.logger.info(f"Skipping stale donation {donation_id}: created_at={created_at}")
                with self._processed_lock:
                    self.processed_donations.add(donation_id)
                    self._processed_order.append(donation_id)
                    if len(self._processed_order) > 2000:
                        to_trim = len(self._processed_order) - 2000
                        for _ in range(to_trim):
                            old = self._processed_order.pop(0)
                            try:
                                self.processed_donations.remove(old)
                            except KeyError:
                                pass
                    # In-memory only; no persistence
                return

            username = donation.get('username', 'Anonymous')
            amount = float(donation.get('amount', 0) or 0)
            currency = donation.get('currency', 'RUB')
            message = donation.get('message', '') or ''

            self.logger.info(f"Processing donation: {username} - {amount} {currency}")
            self.total_donations_processed += 1

            # Convert to RUB for threshold checking
            amount_rub = amount
            if currency != 'RUB':
                try:
                    converted = self.currency_converter.convert_to_rub(amount, currency)
                    if converted is not None:
                        amount_rub = converted
                        self.logger.info(f"Converted {amount} {currency} to {amount_rub:.2f} RUB")
                except Exception as e:
                    self.logger.warning(f"Currency conversion failed: {e}")

            # Threshold check
            threshold = getattr(self.config, 'donation_threshold_rub', 1000)
            if amount_rub >= threshold:
                self.logger.info(f"Donation qualifies for video: {amount_rub:.2f} RUB >= {threshold} RUB")

                donation_info = {
                    'id': donation_id,
                    'username': username,
                    'amount': amount,
                    'currency': currency,
                    'amount_rub': amount_rub,
                    'message': message,
                    'created_at': created_at
                }

                # Mark as processed BEFORE starting generation to avoid duplicates
                with self._processed_lock:
                    self.processed_donations.add(donation_id)
                    self._processed_order.append(donation_id)
                    if len(self._processed_order) > 2000:
                        to_trim = len(self._processed_order) - 2000
                        for _ in range(to_trim):
                            old = self._processed_order.pop(0)
                            try:
                                self.processed_donations.remove(old)
                            except KeyError:
                                pass
                    # In-memory only; no persistence

                # Generate video in background thread to avoid blocking the poller
                def _gen():
                    try:
                        self.logger.info(f"Starting background video generation for donation {donation_id}")
                        video_path = self.video_generator.generate_video(donation_info, amount_rub)
                        if video_path:
                            self.total_videos_generated += 1
                            self.logger.info(f"Video generated for donation {donation_id}: {video_path}")
                        else:
                            self.logger.warning(f"Video generation returned no file for donation {donation_id}")
                    except Exception as e:
                        self.logger.error(f"Error generating video for donation {donation_id}: {e}")
                threading.Thread(target=_gen, daemon=True).start()
            else:
                self.logger.info(f"Donation below threshold: {amount_rub:.2f} RUB < {threshold} RUB")
                with self._processed_lock:
                    self.processed_donations.add(donation_id)
                    self._processed_order.append(donation_id)
                    if len(self._processed_order) > 2000:
                        to_trim = len(self._processed_order) - 2000
                        for _ in range(to_trim):
                            old = self._processed_order.pop(0)
                            try:
                                self.processed_donations.remove(old)
                            except KeyError:
                                pass
                    # In-memory only; no persistence

        except Exception as e:
            self.logger.error(f"Error processing donation: {e}")
    
    def _record_recent(self, donation: Dict[str, Any]) -> None:
        """Store recent donations for UI/history. Keeps the last 100 items."""
        try:
            with self._recent_lock:
                self.recent_donations.append({
                    "id": donation.get("id"),
                    "username": donation.get("username", "Anonymous"),
                    "amount": float(donation.get("amount", 0) or 0),
                    "currency": donation.get("currency", "RUB"),
                    "message": donation.get("message", "") or "",
                    "created_at": donation.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
                if len(self.recent_donations) > 100:
                    # Trim from the start (oldest first)
                    overflow = len(self.recent_donations) - 100
                    del self.recent_donations[:overflow]
        except Exception:
            # Do not break polling if recording fails
            pass

    def get_recent_donations(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return a copy of the most recent donations (up to limit)."""
        with self._recent_lock:
            if limit <= 0:
                return []
            return list(self.recent_donations[-limit:])
    
    def test_api_connection(self) -> Dict[str, Any]:
        """Test the API connection and return status information."""
        if not self.api_token:
            return {
                'success': False,
                'error': 'API token not configured'
            }
        
        try:
            donations = self._fetch_donations()
            if donations is not None:
                return {
                    'success': True,
                    'status': 'Connected successfully',
                    'total_donations': len(donations),
                    'api_errors': self.api_errors,
                    'last_poll': self.last_poll_time.isoformat() if self.last_poll_time else None
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to fetch donations - check logs for details'
                }
        except Exception as e:
            return {
                'success': False,
                'error': f'Connection test failed: {str(e)}'
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get polling service statistics."""
        return {
            'is_running': self.is_running,
            'has_token': bool(self.api_token),
            'total_donations_processed': self.total_donations_processed,
            'total_videos_generated': self.total_videos_generated,
            'last_poll_time': self.last_poll_time.isoformat() if self.last_poll_time else None,
            'api_errors': self.api_errors,
            'processed_donations_count': len(self.processed_donations)
        }
