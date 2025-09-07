"""
Configuration management for the Donation Celebration App.
Handles environment variables and application settings.
"""

import os
import logging

class Config:
    """Application configuration class."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # DonationAlerts configuration
        self.donationalerts_api_token = None
        # OAuth client config
        # Support multiple env var names for convenience
        # Prefer explicit DONATIONALERTS_CLIENT_ID/SECRET, but fall back to DA_CLIENT_ID/SECRET, then DONATIONALERTS_API_KEY as client_id
        self.donationalerts_client_id = os.getenv('DA_CLIENT_ID')
        self.donationalerts_client_secret = os.getenv('DA_CLIENT_SECRET')
        # Use provided redirect URI or default to local server
        default_port = os.getenv('PORT', '5002')
        self.donationalerts_redirect_uri = f"http://localhost:{default_port}/api/da/oauth/callback"

        # OAuth token storage (in-memory)
        # Access token used by API client/poller
        self.donation_alerts_token = ''
        # Refresh token and expiry (optional)
        self.donationalerts_refresh_token = ''
        # (removed donationalerts_expires_at and donationalerts_token_type per vulture)

        # AIML API configuration (replaces Google Cloud)
        self.aiml_api_key = os.getenv('AIMLAPI_KEY')
        if not self.aiml_api_key:
            self.logger.warning("AIMLAPI_KEY not found - video generation will not work")
        
        # Currency conversion (handled separately; no env vars)
        
        # Donation threshold
        self.donation_threshold_rub = 1000.0
        
        # Additional settings for UI configuration
        self.donation_threshold_amount = 1000.0  # User-configurable amount
        self.donation_threshold_currency = 'RUB'  # User-configurable currency
        
        # Video generation settings for AIML API
        # (video_duration_seconds, video_aspect_ratio, video_resolution removed)
        
        # File paths
        self.videos_directory = 'generated_videos'
        self.ensure_directories()
        
        # Video prompts based on donation amounts
        self.video_prompts = {
            1000: "A spectacular celebration with golden confetti falling from the sky, sparkling lights, and festive decorations. Camera slowly zooms in on celebration scene with warm, joyful lighting.",
            2000: "An epic fireworks display lighting up the night sky with brilliant colors, golden sparks cascading down like a waterfall of light, celebration atmosphere with magical sparkles.",
            5000: "A grand royal celebration in a magnificent palace hall with golden chandeliers, flowing silk banners, rose petals falling gracefully, and majestic orchestral atmosphere.",
            10000: "An otherworldly cosmic celebration with stars exploding into rainbow colors, nebula clouds dancing through space, celestial music visualized as light waves across the universe.",
            50000: "A legendary dragon made of pure golden light soaring through crystal clouds, breathing rainbow fire that transforms into celebration fireworks, epic fantasy atmosphere with orchestral crescendo."
        }
        
        self.logger.info("Configuration loaded successfully")
    
    def ensure_directories(self):
        """Create necessary directories if they don't exist."""
        directories = [self.videos_directory, 'logs']
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    def get_video_prompt(self, amount_rub):
        """Get appropriate video prompt based on donation amount."""
        # Find the highest threshold that the amount meets
        applicable_thresholds = [threshold for threshold in sorted(self.video_prompts.keys()) if amount_rub >= threshold]
        
        if applicable_thresholds:
            threshold = applicable_thresholds[-1]
            base_prompt = self.video_prompts[threshold]
            
            # Add amount-specific enhancement
            if amount_rub >= 50000:
                enhancement = f" This celebration honors an extraordinary donation of {amount_rub:,.0f} RUB - truly legendary generosity!"
            elif amount_rub >= 10000:
                enhancement = f" This magnificent celebration celebrates {amount_rub:,.0f} RUB of incredible generosity!"
            elif amount_rub >= 5000:
                enhancement = f" This grand celebration honors {amount_rub:,.0f} RUB of amazing support!"
            elif amount_rub >= 2000:
                enhancement = f" This epic celebration is for {amount_rub:,.0f} RUB of wonderful generosity!"
            else:
                enhancement = f" This beautiful celebration thanks the donor for {amount_rub:,.0f} RUB!"
            
            return base_prompt + enhancement
        
        return f"A beautiful celebration with sparkling lights and festive atmosphere, honoring a generous donation of {amount_rub:,.0f} RUB."
    
    def validate(self):
        """Validate configuration settings."""
        required_fields = [
            ('aiml_api_key', 'AIMLAPI_KEY')
        ]
        
        missing = []
        for field_name, env_name in required_fields:
            if not getattr(self, field_name):
                missing.append(env_name)
        
        if missing:
            self.logger.error(f"Missing required configuration: {missing}")
            return False
        
        return True
