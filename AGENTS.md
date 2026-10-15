# AGENTS.md — instructions for AI coding agents

Read this before changing anything in this repository.

## What this project is

Stock Research Assistant: a web app where an AI agent answers market questions
using Alpha Vantage data over MCP. See `product-spec.md` for the features and
the guardrails.

## Layout

| Path | Contents |
|------|----------|
| `openapi.yaml` | **API contract and source of truth.** Change it first, then the code. |
| `backend/` | FastAPI + SQLAlchemy + OpenAI Agents SDK (Python 3.13, managed with `uv`) |
| `frontend/` | React + Vite + TypeScript. All HTTP calls go through `src/api/client.ts`. |
| `mcp-server/` | This project's own MCP server, which exposes sessions and the watchlist |
| `docs/` | Architecture, AI workflow log, permissions, extension pack |
| `security/` | Security scan outputs and the AI tool/data policy |
| `ops/` | Runbook and operational diagnosis output |

## Rules

1. **Contract first.** To add or change an endpoint, edit `openapi.yaml`, run
   `uvx openapi-spec-validator openapi.yaml`, then update the backend,
   regenerate the frontend types, and update the tests, in that order.
   `tests/integration/test_contract_coverage.py` fails if the routes and the
   contract disagree.
2a. **Schema changes need a migration:** after editing `app/models.py`, run
   `uv run alembic revision --autogenerate -m "..."` and review the generated file.
2. **Never call real external APIs in tests.** Use the fake agent
   (`backend/app/agent/fake.py`). CI has no OpenAI or Alpha Vantage keys.
3. **Unit tests** go in `backend/tests/unit/`. **Integration tests** (real HTTP
   and a real database) go in `backend/tests/integration/`. Keep them separate.
4. **No secrets in code, logs, or commits.** Keys come from environment
   variables only, and `.env` is gitignored. Never log full request URLs
   to Alpha Vantage, because the API key can appear in the query string.
5. **The agent connects only to the Alpha Vantage MCP server.** Do not add
   filesystem, shell, or other local-access MCP servers to the runtime agent.
6. **Frontend:** no `fetch` calls outside `src/api/client.ts` (ESLint enforces
   this). Components get the client through `useApi()` so tests can inject
   `createFakeApi()`. Never edit `src/api/schema.d.ts` by hand.
7. Keep changes small and run the relevant tests before saying something works.
   See `docs/testing.md` for which test layer a change belongs in.

## Commands

```bash
# backend
cd backend && uv sync && uv run pytest tests/unit
cd backend && uv run pytest tests/integration   # SQLite by default; set TEST_DATABASE_URL for Postgres
cd backend && uv run alembic upgrade head        # apply migrations to DATABASE_URL
cd backend && uv run ruff check . && uv run ruff format --check .
cd backend && uv run uvicorn app.main:create_app --factory --reload

# frontend
cd frontend && npm ci && npm test && npm run dev
cd frontend && npm run gen:api      # regenerate src/api/schema.d.ts after changing openapi.yaml
cd frontend && npm run typecheck && npm run lint
cd frontend && npm run e2e          # Playwright end-to-end (own servers on 8001/4173)

# everything (http://localhost:8080; fake agent unless .env says otherwise)
docker compose up --build
# integration tests on Postgres (uses the separate app_test database)
TEST_DATABASE_URL=postgresql://app:app@localhost:5432/app_test uv run pytest tests/integration
```

## AI workflow log

After meaningful AI-assisted work, add an entry to `docs/ai-workflow.md`
covering what was asked, what was produced, what was reviewed or changed by
hand, and how it was verified.
