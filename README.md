# StreamSpark 🎥✨

Automated Donation Celebration Video Generator (FastAPI)

StreamSpark is a FastAPI application that monitors DonationAlerts for new donations above a configurable threshold and generates celebration videos (AIML Veo3). An OBS browser widget is included to play videos on stream.

- Local Dashboard: http://localhost:5002/dashboard
- OBS Widget: http://localhost:5002/widget
- Status: http://localhost:5002/status

## Quick Start (make-first)

Requirements:
- Python 3.11+
- Recommended: [uv](https://github.com/astral-sh/uv) (optional)
- Installed `make`
  - Windows: use Git Bash (Git for Windows) or WSL to run `make`

Steps:
```bash
# 1) See available commands
make help

# 2) Install dependencies (uses uv if available; otherwise venv + pip)
make install

# 3) Create local .env from example
make env
# edit .env as needed

# 4a) Start in development mode (auto-reload)
make dev

# 4b) Normal start
make run
```

Open:
- Dashboard: http://localhost:5002/dashboard
- OBS Widget: http://localhost:5002/widget
- Status/Diagnostics: http://localhost:5002/status

### Make Commands

- install — install dependencies (uv sync or venv + pip)
- env — create .env from .env.example if missing
- dev — run with auto-reload (uvicorn --reload)
- run — run server (uvicorn)
- serve — alias for run
- test — run pytest (if installed)
- format — run black (if installed)
- lint — run ruff (if installed)
- clean — remove caches/logs/temp files
- clean-logs — clean ./logs (keep .gitkeep)
- clean-videos — clean ./generated_videos (keep .gitkeep)
- clean-db — remove local sqlite files
- env-print — print key environment variables

Notes:
- On Windows, run `make` in Git Bash/WSL (scripts use POSIX utils: cp, find, etc).
- You can override PORT: `make dev PORT=5003`.

### Alternative Manual Run (optional)

If you don’t want to use `make`, you can run manually:

Install dependencies:
```bash
# recommended
uv sync

# or pip
pip install -r requirements.txt
```

Prepare environment variables:
```bash
cp .env.example .env
# edit .env as needed
```

Run server:
```bash
python -m uvicorn main_fastapi:app --reload --port 5002
# or
python main_fastapi.py
```

## Features

- DonationAlerts integration:
  - OAuth flow (login, callback, disconnect)
  - Alternative: direct API token without OAuth
  - Background poller (start/stop), health-check
- Video generation via AIML API (Veo3)
- Modular FastAPI routers (logs, videos, settings, generation, polling, OAuth, pages)
- OBS browser widget (browser source) to play videos
- Multi-currency (conversion to RUB for threshold logic) with simple in-memory rate cache
- In-memory configuration (no database; nothing written to disk)
- Simple admin endpoints (system prompt, thresholds)
- Basic logs and stats for diagnostics

## Environment Variables

See .env.example for the full list. Key variables:

Video generation:
- AIMLAPI_KEY — AIML (Veo3) API key. Without it, generation is disabled.

Threshold/conversion:
- DONATION_THRESHOLD_RUB — minimum amount (in RUB) to trigger generation (default 1000)
- EXCHANGE_RATE_API_KEY — optional API key for exchange rates provider. If omitted, a public free-tier endpoint will be used. Rate caching is in-memory only (TTL 5 minutes by default, override with EXCHANGE_RATE_CACHE_MINUTES).

DonationAlerts (OAuth, recommended):
- DONATIONALERTS_CLIENT_ID (or DA_CLIENT_ID, or DONATIONALERTS_API_KEY)
- DONATIONALERTS_CLIENT_SECRET (or DA_CLIENT_SECRET)
- DONATIONALERTS_REDIRECT_URI (or DA_REDIRECT_URI) (default http://localhost:${PORT}/api/da/oauth/callback)

DonationAlerts (direct token, OAuth alternative):
- DONATIONALERTS_API_TOKEN — can be set in .env or via POST /api/access-token after the server starts.
  - Important: the token is stored in process memory; after restart it must be set again (or provided via env).

Other:
- PORT — development port (default 5002)

## OBS Integration

Add a Browser Source in OBS:
- URL: http://localhost:5002/widget

Queue a specific video for the widget to play:
```bash
curl -X POST http://localhost:5002/api/play-in-obs \
  -H "Content-Type: application/json" \
  -d '{"filename":"your_video.mp4"}'
```

## API Overview

Base pages:
- GET / → redirect to /dashboard
- GET /dashboard → dashboard UI
- GET /landing → demo landing
- GET /status → app status and useful links

Logs/Stats:
- GET /api/logs?since=&show_ip= → latest logs (including parsed uvicorn.access)
- GET /api/stats → aggregated stats (video count, poller status, etc.)

Videos:
- GET /api/latest-video → metadata of the latest video (for widget)
- GET /api/recent-videos → up to 5 most recent
- GET /api/all-videos → list all generated
- DELETE /api/delete-video/{filename} → delete
- POST /api/play-in-obs → queue a video for the widget
  - Body: {"filename":"name.mp4"} or {"url":"/videos/name.mp4"}

Settings:
- GET /api/settings → snapshot of app settings
- GET /api/connection-status → DonationAlerts connection status
- GET /api/threshold → current threshold (RUB)
- POST /api/threshold → set threshold; converts if another currency is provided
  - Body: {"threshold": 1500} or {"amount": 20, "currency": "USD"}
- GET /api/access-token → check if token is present
- POST /api/access-token → set API token (start/stop poller)
  - Body: {"access_token": "..." }
- POST /api/donation-alerts-token → alternative token setter (same behavior)
- GET /api/aiml-status → diagnostics (AIML key presence, poller status, system prompt preview)

Generation:
- GET /api/generation-status → background generation status
- GET /api/system-prompt → get system prompt
- POST /api/system-prompt → update system prompt
  - Body: {"prompt": "Your system prompt"}
- POST /api/generate-video → start custom generation (in background)
  - Body: {"prompt": "Your prompt"}
- POST /api/generate-veo-video → generation via Veo (duration/quality — compatibility for now)
  - Body: {"prompt": "Your prompt", "duration": "5s", "quality": "preview"}

Polling (DonationAlerts):
- GET /api/donations → latest donations seen by the poller (in-memory buffer)
- GET /api/test-donation-alerts → connectivity test; on success, auto-start the poller
- POST /api/start-polling → start poller (token required)
- POST /api/stop-polling → stop poller

DonationAlerts OAuth:
- GET /api/da/oauth/debug → current OAuth config (no secrets)
- GET /api/da/oauth/login → redirect to OAuth
- GET /api/da/oauth/callback → handle callback, apply tokens, start poller
- POST /api/da/disconnect → clear tokens in memory, stop poller

## Architecture

Entry point:
- main_fastapi.py — app factory, static/templates mounting, routers, startup/shutdown hooks, status and test endpoints

Core:
- core/container.py — service initialization, apply config from env/in-memory, auto-start poller if token present
- core/logging_utils.py — logging setup and recent logs access
- core/state.py — global access to the container

Routers:
- routes/pages.py — pages (landing, dashboard)
- routes/widget_videos.py — serve videos for the widget
- routes/api_logs.py — logs and stats
- routes/api_videos.py — lists/deletion/play in OBS
- routes/api_settings.py — settings, tokens, threshold, connection, AIML status
- routes/api_generation.py — system prompt, custom generation/status
- routes/api_polling.py — donations, test/start/stop poller
- routes/donation_alerts_oauth.py — DonationAlerts OAuth endpoints

Services:
- services/aiml_client.py — AIML Veo3 HTTP client (start, polling, download)
- services/video_generator.py — prompt/path orchestration, delegates to AIMLClient
- services/donation_alerts_client.py — DonationAlerts HTTP client (fetch/refresh), store tokens in Config (in-memory)
- services/donation_alerts_poller.py — background poller using token + threshold; in-memory buffer and counters
- services/currency_converter.py — conversion to RUB, in-memory TTL cache (no DB)
- services/obs_widget.py — OBS widget service

Other:
- utils/files.py — safe video filename validator
- static/, templates/, generated_videos/

Notes:
- Configuration/tokens/state — in memory only. After restart, re-set values (or provide via .env).
- File config_storage.py is a deprecated stub kept for compatibility, not for storage.

## Project Structure

```
StreamSpark/
├─ main_fastapi.py
├─ core/
│  ├─ container.py
│  ├─ logging_utils.py
│  └─ state.py
├─ routes/
│  ├─ pages.py
│  ├─ widget_videos.py
│  ├─ api_logs.py
│  ├─ api_videos.py
│  ├─ api_settings.py
│  ├─ api_generation.py
│  ├─ api_polling.py
│  └─ donation_alerts_oauth.py
├─ services/
│  ├─ aiml_client.py
│  ├─ video_generator.py
│  ├─ donation_alerts_client.py
│  ├─ donation_alerts_poller.py
│  ├─ currency_converter.py
│  └─ obs_widget.py
├─ utils/files.py
├─ templates/ ... (Jinja2)
├─ static/ ... (JS/CSS)
├─ generated_videos/ ... (output)
├─ config.py
├─ config_storage.py (deprecated stub)
├─ requirements.txt
├─ pyproject.toml
├─ uv.lock
└─ README.md
```

## Development

Run with hot-reload:
```bash
make dev
```

Logs:
- API: GET /api/logs
- Files: ./logs directory (if enabled in logging_utils)

Diagnostics:
- GET /api/aiml-status
- GET /api/generation-status
- GET /status

## Examples

Set threshold (USD → converted to RUB on the fly):
```bash
curl -X POST http://localhost:5002/api/threshold \
  -H "Content-Type: application/json" \
  -d '{"amount": 20, "currency": "USD"}'
```

Set direct DonationAlerts token (no OAuth):
```bash
curl -X POST http://localhost:5002/api/access-token \
  -H "Content-Type: application/json" \
  -d '{"access_token":"YOUR_TOKEN"}'
```

Start poller (token required):
```bash
curl -X POST http://localhost:5002/api/start-polling
```

## Troubleshooting

- Missing AIMLAPI_KEY: video generation will be disabled; set the variable and restart the server.
- 401 from DonationAlerts: check OAuth credentials or direct token. Use GET /api/test-donation-alerts to verify and auto-start the poller.
- Behavior after restart: configuration is in memory; after restart, set token/threshold again via API or env vars.
- Port already in use: change PORT in .env or pass --port to uvicorn.
- Windows: if `make` is not found, install Git for Windows and use Git Bash, or run the alternative commands manually.

## License

MIT
