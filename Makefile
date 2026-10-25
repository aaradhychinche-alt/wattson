SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: help install test lint typecheck check demo api worker temporal migrate

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

install: ## Install Python dependencies (including dev)
	uv sync --extra dev

test: ## Run the full test suite (unit, API, workflow time-skipping)
	uv run pytest

lint: ## Ruff static checks
	uv run ruff check backend tests

typecheck: ## Mypy static types
	uv run mypy backend/wattson

check: lint typecheck test ## Run all local checks

temporal: ## Start a local Temporal dev server
	temporal server start-dev --db-filename .data/temporal.db

worker: ## Run the Temporal worker
	uv run python -m wattson.worker

api: ## Run the API on port 8000
	uv run uvicorn wattson.api.app:app --port 8000

migrate: ## Apply Alembic migrations
	uv run alembic upgrade head

ifeq ($(OS),Windows_NT)
demo: ## One-command end-to-end demo (Windows PowerShell)
	powershell -ExecutionPolicy Bypass -File scripts/demo.ps1
else
demo: ## One-command end-to-end demo (POSIX)
	bash scripts/demo.sh
endif
