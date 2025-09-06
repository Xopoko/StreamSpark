#!/usr/bin/env python3
"""
Legacy entrypoint (Flask) replaced by FastAPI.

This file now serves as a compatibility shim to run the new FastAPI app.
Use `make run` or run uvicorn directly:

  uvicorn main_fastapi:app --host 0.0.0.0 --port 5002

All previous Flask routes have been ported to FastAPI in:
- main_fastapi.py (ASGI entrypoint)
- routes/ (modular routers)
- core/ (logging + container/DI)

Note: The old Flask-specific code has been removed from this file.
"""

import os
import sys

if __name__ == "__main__":
    try:
        import uvicorn  # type: ignore
    except Exception:
        print("Uvicorn is not installed. Install dependencies first:")
        print('  - With uv:   uv sync')
        print('  - Or pip:    py -3 -m venv .venv && .venv\\Scripts\\python -m pip install -U pip && '
              '.venv\\Scripts\\python -m pip install fastapi "uvicorn[standard]" jinja2 aiofiles requests typing-extensions python-dotenv')
        sys.exit(1)

    port = int(os.environ.get("PORT", 5002))
    print("\n" + "=" * 60)
    print("🎉 DONATION CELEBRATION APP (FastAPI) STARTING 🎉")
    print("=" * 60)
    print(f"🎬 OBS Widget URL: http://0.0.0.0:{port}/widget")
    print(f"📊 Status URL: http://0.0.0.0:{port}/status")
    print("=" * 60)
    print("Tip: Use `make run` to start the server via uvicorn.")
    print("=" * 60 + "\n")

    uvicorn.run("main_fastapi:app", host="0.0.0.0", port=port, log_level="info")
