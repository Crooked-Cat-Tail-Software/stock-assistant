# AGENTS.md: instructions for AI coding agents

Start here. This file is the entry point: it states the project, the rules
that always apply, and **which focused document to read for the task at
hand**. Keep it short; put details in the linked docs.

## What this project is

**Stock Research Assistant:** a web app where an AI agent answers market
questions using live market data (yfinance first, Alpha Vantage over MCP for
news and as fallback), with saved conversations and
a watchlist. React frontend, FastAPI backend, Postgres, deployed on Render.
Live at <https://stock-assistant-web.onrender.com>.

## Read this when…

| When you are… | Read |
|---------------|------|
| Starting any task, or deciding what "done" means | [docs/process.md](docs/process.md): issue → plan → branch → review → PR → deploy, plus the definition of done |
| Working out who should do a step, or which specialist to call | [docs/agent-team.md](docs/agent-team.md): roles, limits, hand-offs; subagents in [`.claude/agents/`](.claude/agents/) |
| Changing or adding behavior | [product-spec.md](product-spec.md): features F1–F6, guardrails, acceptance criteria |
| Changing an endpoint, request, or response | [openapi.yaml](openapi.yaml): the API contract and source of truth |
| Writing or placing tests | [docs/testing.md](docs/testing.md): the four layers, feature-to-test map, how to run |
| Touching Docker, CI, Render, nginx, or production | [docs/deployment.md](docs/deployment.md): CD flow, security model, client-IP chain, known gaps |
| Finishing a piece of AI-assisted work | [docs/ai-workflow.md](docs/ai-workflow.md): add a log entry |
| Looking for open work | [GitHub Issues](https://github.com/Crooked-Cat-Tail-Software/stock-assistant/issues): the task tracker; every task has acceptance criteria |

## Layout

| Path | Contents |
|------|----------|
| `openapi.yaml` | API contract. Change it first, then the code. |
| `product-spec.md` | Problem, features, guardrails, acceptance criteria |
| `backend/` | FastAPI + SQLAlchemy + Alembic + OpenAI Agents SDK (Python 3.13, `uv`). Agent code in `app/agent/` |
| `frontend/` | React + Vite + TypeScript. All HTTP calls go through `src/api/client.ts`. Playwright tests in `e2e/` |
| `docs/` | process, agent team, testing, deployment, AI workflow log |
| `.claude/agents/` | Specialist subagents: contract-reviewer, test-engineer, security-reviewer, deploy-verifier |
| `.github/workflows/` | `ci.yml` (all checks), `verify-deploy.yml` (production check after each deploy) |
| `ops/` | `scripts/wait-for-commit.sh` (deploy verification), `postgres-init/` (Compose test database) |
| `security/` | `gitleaks-report.json` (secret scan of the full history) |
| `docker-compose.yml`, `render.yaml` | Local full stack; production infrastructure (Render Blueprint) |
| `Makefile` | `make help` lists the commands |

## Rules that always apply

1. **Work from an issue.** Comment your plan on it before starting, and
   reference it in commits (`Refs #N`) and the PR (`Closes #N`).
2. **Contract first.** For API changes: edit `openapi.yaml` → run
   `uvx openapi-spec-validator openapi.yaml` → backend → `npm run gen:api` →
   frontend → tests. `test_contract_coverage.py` fails if routes and the
   contract disagree.
3. **Schema changes need a migration:** after editing `backend/app/models.py`,
   run `uv run alembic revision --autogenerate -m "..."` and review the file.
4. **Never call real external APIs in tests.** Use `FakeAgent`,
   `make_client(agent=...)`, or `createFakeApi()`. CI has no keys.
5. **Tests go in the right layer** (see [docs/testing.md](docs/testing.md)),
   and a new test must be shown to fail without the change it guards.
6. **No secrets in code, logs, or commits.** Keys come from environment
   variables only. Never log Alpha Vantage URLs (the key is in the query
   string). In `render.yaml` secrets are `sync: false`. In workflows they're
   `secrets.*`.
7. **The runtime agent has read-only market-data tools only:** the yfinance
   tools in `backend/app/agent/market_tools.py` and the Alpha Vantage MCP
   server. No filesystem, shell, or other local-access tools. New tools must
   validate inputs, time out, and return errors as results (see `market_tools.py`).
8. **Frontend:** no `fetch` outside `src/api/client.ts` (ESLint enforces it).
   Components use `useApi()`. Never edit `src/api/schema.d.ts` by hand.
9. **Commit `render.yaml` changes on their own.** Render applies them without
   waiting for CI.
10. **Ask the human** before anything involving an account, a secret, money,
    or public posting, and before merging to `main`.

## Commands

```bash
make help        # list everything below
make install     # backend (uv sync) + frontend (npm ci)
make test        # all unit + integration tests, backend and frontend (no keys or services needed)
make test-all    # + Playwright end-to-end
make lint        # ruff, ESLint, TypeScript
make up / down   # full stack in Docker → http://localhost:8080 (fake agent unless .env says otherwise)
```

Single suites and other tasks:

```bash
cd backend && uv run pytest tests/unit                  # or tests/integration
TEST_DATABASE_URL=postgresql://app:app@localhost:5432/app_test uv run pytest tests/integration  # on Postgres (make up first)
cd backend && uv run alembic upgrade head               # apply migrations to DATABASE_URL
cd backend && uv run uvicorn app.main:create_app --factory --reload   # backend on :8000
cd frontend && npm run dev                              # frontend on :5173 (proxies /api to :8000)
cd frontend && npm run gen:api                          # regenerate types after changing openapi.yaml
```
