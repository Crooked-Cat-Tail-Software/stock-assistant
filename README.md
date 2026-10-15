# Stock Research Assistant

Ask market questions in plain English and get answers backed by live Alpha
Vantage data, with saved conversations and a personal watchlist.

> Final project for [AI Dev Tools Zoomcamp](https://github.com/DataTalksClub/ai-dev-tools-zoomcamp).
> Work in progress.

## Problem

See [product-spec.md](product-spec.md) for the full problem statement,
features, guardrails, and acceptance criteria.

## Architecture

_TODO (Phase 9): diagram, plus the roles of the frontend, backend, database,
Docker, and CI/CD._

## Running locally

Full Docker setup: _TODO (Phase 5)._ To run the backend on its own:

```bash
cd backend
uv sync
uv run alembic upgrade head                                 # create/upgrade the database
uv run uvicorn app.main:create_app --factory --reload       # http://localhost:8000/docs
```

With no `.env` file, the backend runs with `AGENT_MODE=fake`, which needs no API
keys. For real answers, copy `.env.example` to `.env`, set `AGENT_MODE=openai`,
and add your OpenAI and Alpha Vantage keys.

## Testing

```bash
cd backend
uv run pytest tests/unit          # business logic, no HTTP (in-memory SQLite)
uv run pytest tests/integration   # real HTTP + real DB built by migrations
```

Integration tests check every response against `openapi.yaml` and fail if the
implemented routes drift from the contract. They use SQLite by default; set
`TEST_DATABASE_URL=postgresql://...` to run them against Postgres. No test ever
calls OpenAI or Alpha Vantage; a fake agent stands in.

## Deployment

_TODO (Phase 7)._

## AI-assisted development

See [docs/ai-workflow.md](docs/ai-workflow.md) and [AGENTS.md](AGENTS.md).

## Credits

The agent code is adapted from the MIT-licensed
[Alpha Vantage MCP agent example](https://github.com/alphavantage/alpha_vantage_mcp/tree/main/examples/agent).
See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
