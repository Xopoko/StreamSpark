import sys
import os
import types
import pytest
from fastapi.testclient import TestClient

# Ensure project root is on sys.path so tests can import application modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import main_fastapi


@pytest.fixture
def stub_container():
    # Minimal stub container used by the app during tests
    cfg = types.SimpleNamespace()
    cfg.donation_threshold_rub = 1000.0
    cfg.donation_threshold_amount = 1000.0
    cfg.donation_threshold_currency = "RUB"

    class CurrencyConverterStub:
        def convert_to_rub(self, amount: float, from_currency: str):
            # Simple deterministic conversion for tests:
            # if already RUB, return same amount, else simulate conversion (multiply by 70)
            if from_currency.upper() == "RUB":
                return float(amount)
            try:
                return float(amount) * 70.0
            except Exception:
                return None

    class VideoGeneratorStub:
        def __init__(self):
            # control behavior in tests by overwriting this attribute
            self.return_path = "/generated_videos/test.mp4"

        def generate_video(self, donation_info, amount_rub, custom_prompt=None):
            return self.return_path

    class DonationPollerStub:
        def start_polling(self):
            self._running = True

        def stop_polling(self):
            self._running = False

        def set_api_token(self, token):
            self.token = token

    currency_converter = CurrencyConverterStub()
    video_generator = VideoGeneratorStub()
    donation_poller = DonationPollerStub()
    obs_widget = types.SimpleNamespace()

    container = types.SimpleNamespace(
        config=cfg,
        currency_converter=currency_converter,
        video_generator=video_generator,
        donation_poller=donation_poller,
        obs_widget=obs_widget,
    )
    return container


@pytest.fixture
def client(monkeypatch, stub_container):
    # Patch the init_container used by main_fastapi's startup handler so the app uses our stub
    monkeypatch.setattr(main_fastapi, "init_container", lambda: stub_container)
    app = main_fastapi.create_app()
    with TestClient(app) as c:
        yield c
