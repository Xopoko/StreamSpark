# StreamSpark - Makefile
# Default goal
.DEFAULT_GOAL := help

# Python command auto-detect (works on Windows, WSL, Linux)
OS_NAME := $(OS)
UNAME_S := $(shell uname -s 2>/dev/null)

# Default to 'python' so activated virtualenv is respected on POSIX/WSL
PYTHON := python

# Prefer venv executables if present (POSIX)
ifneq ("$(wildcard .venv/bin/python)","")
  PYTHON := .venv/bin/python
endif

# On native Windows, prefer Scripts/python.exe if available
ifeq ($(OS_NAME),Windows_NT)
  ifneq ("$(wildcard .venv/Scripts/python.exe)","")
    PYTHON := .venv/Scripts/python.exe
  endif
endif

PIP    := $(PYTHON) -m pip
PORT   ?= 5002

.PHONY: help env install uv-sync uv-lock run dev serve test clean clean-logs clean-videos clean-db format lint env-print

help: ## Show this help
	@echo "Available targets:"
	@awk 'BEGIN {FS = ":.*##"; printf "  \033[1m%-22s\033[0m %s\n", "Target", "Description"} /^[a-zA-Z0-9_%-]+:.*##/ { printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

env: ## Create local .env from example if missing
	@if [ ! -f .env ]; then cp .env.example .env && echo "Created .env from .env.example"; else echo ".env already exists"; fi

install: ## Install dependencies (cross-platform: use scripts/install.py)
	@echo "[install] Running cross-platform installer via Python script"
	@$(PYTHON) scripts/install.py

uv-sync: ## Sync environment using uv (uses uv.lock/pyproject.toml)
	@uv sync

uv-lock: ## Update uv.lock (refresh locked versions)
	@uv lock -U

run: ## Run the FastAPI app (main_fastapi.py) on PORT=$(PORT)
	@echo "[run] Starting FastAPI app on port $(PORT)"
	@$(PYTHON) -m uvicorn main_fastapi:app --host 0.0.0.0 --port $(PORT) --log-level info

dev: ## Run with auto-reload (development mode) on PORT=$(PORT)
	@echo "[dev] Starting FastAPI app with --reload on port $(PORT)"
	@$(PYTHON) -m uvicorn main_fastapi:app --host 0.0.0.0 --port $(PORT) --reload --log-level info

serve: run ## Alias for run


test: ## Run tests (pytest if available)
	@if $(PYTHON) -c "import pytest" >/dev/null 2>&1; then \
		echo "[test] Running pytest"; \
		$(PYTHON) -m pytest -q; \
	else \
		echo "[test] pytest not installed. To install: '$(PIP) install pytest'"; \
	fi

format: ## Format code with black (if installed)
	@if $(PYTHON) -c "import black" >/dev/null 2>&1; then \
		echo "[format] Running black"; \
		$(PYTHON) -m black .; \
	else \
		echo "[format] black not installed. To install: '$(PIP) install black'"; \
	fi

lint: ## Lint code with ruff (if installed)
	@if $(PYTHON) -c "import ruff" >/dev/null 2>&1; then \
		echo "[lint] Running ruff"; \
		$(PYTHON) -m ruff check .; \
	else \
		echo "[lint] ruff not installed. To install: '$(PIP) install ruff'"; \
	fi

env-print: ## Print important env vars resolved at runtime
	@$(PYTHON) -c 'import os; keys=["SESSION_SECRET","AIMLAPI_KEY","EXCHANGE_RATE_API_KEY","DONATION_THRESHOLD_RUB","DA_CLIENT_ID","DA_CLIENT_SECRET","DONATIONALERTS_API_TOKEN","PORT"]; print("Resolved environment values:"); [print(f"{k}=", os.environ.get(k,"")) for k in keys]'

clean: clean-logs clean-videos clean-db ## Remove caches, logs (keep .gitkeep), generated videos (keep .gitkeep) and local DB
	@echo "[clean] Removing Python caches"
	@find . -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.py[cod]" -delete 2>/dev/null || true
	@rm -rf .pytest_cache .coverage htmlcov 2>/dev/null || true

clean-logs: ## Clean logs directory except .gitkeep
	@echo "[clean-logs] Cleaning logs"
	@mkdir -p logs
	@find logs -type f ! -name ".gitkeep" -delete 2>/dev/null || true

clean-videos: ## Clean generated_videos except .gitkeep
	@echo "[clean-videos] Cleaning generated_videos"
	@mkdir -p generated_videos
	@find generated_videos -type f ! -name ".gitkeep" -delete 2>/dev/null || true

clean-db: ## Remove local sqlite DB files
	@echo "[clean-db] Removing local DB files"
	@rm -f local.db *.sqlite *.sqlite3 2>/dev/null || true
