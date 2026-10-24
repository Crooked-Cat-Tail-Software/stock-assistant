# Common tasks. Run `make help` to list them.
#
# `make test` needs no API keys, Docker, or running services: backend tests use
# SQLite and the fake agent; frontend tests use an in-memory fake API.

.DEFAULT_GOAL := help
.PHONY: help install test test-backend test-frontend test-e2e test-all lint up down

help: ## List available commands
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  make %-14s %s\n", $$1, $$2}'

install: ## Install backend and frontend dependencies
	cd backend && uv sync
	cd frontend && npm ci

test: test-backend test-frontend ## Run all unit and integration tests (backend + frontend)
	@echo "✓ All unit and integration tests passed"

test-backend: ## Backend unit tests, then integration tests (real HTTP + DB built by migrations)
	cd backend && uv run pytest tests/unit -q
	cd backend && uv run pytest tests/integration -q

test-frontend: ## Frontend unit tests (API client, validation, UI flows)
	cd frontend && npm test

test-e2e: ## End-to-end tests in a real browser (starts its own servers)
	cd frontend && npm run e2e

test-all: test test-e2e ## Everything, including end-to-end
	@echo "✓ All tests passed, including end-to-end"

lint: ## Linters and type checks
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run lint && npm run typecheck

up: ## Start the full stack with Docker Compose (http://localhost:8080)
	docker compose up --build -d --wait

down: ## Stop the stack (data is kept)
	docker compose down
