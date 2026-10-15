# AI-assisted development workflow

How AI tools were used to build this project: what was delegated, which
context files guided the AI, what was reviewed by hand, and how each step was
verified.

## Tools and context files

- **Claude Code** (desktop app): planning, scaffolding, code generation
- **Context files:** `AGENTS.md` (rules for any AI agent; `CLAUDE.md` imports
  it), `product-spec.md`, and `openapi.yaml`

## Log

### 2026-10-15 — Project selection and Phase 1 (spec and contract)

**Asked:** Could the Alpha Vantage MCP agent example be adapted to meet the
course project requirements?

**AI did:**
- Compared the example (a CLI-only Python agent) with the 14 rubric criteria
  and estimated that, as-is, it would score about 4–6 of 30
- Reviewed my existing `stock-market-analytics` repo as an alternative base and
  rejected it (notebooks for a different course, with no web components)
- Read the example's source and found three design issues: an unsafe
  `filesystem` MCP server, built-in SQLite session storage, and an MCP
  connection tied to the CLI's lifetime
- Drafted `product-spec.md`, `openapi.yaml`, and `AGENTS.md`

**My decisions:** OpenAI as the AI provider, Render or Railway for
deployment, and a new repo rather than reusing the old one.

**Verified:**
- `uvx openapi-spec-validator openapi.yaml` → OK
- Diffed `THIRD_PARTY_NOTICES.md` against the upstream MIT `LICENSE` → identical
- Caught and fixed a mismatch between the spec and the contract (the spec said
  tickers were "uppercase", while the contract accepts lowercase and
  uppercases it)

**Reviewed by hand:** _TODO (me): read through the spec and contract and note
any changes here._

### 2026-10-15 — Phase 2: backend

**Asked:** Build the FastAPI backend following `openapi.yaml`.

**AI did:**
- Checked the installed OpenAI Agents SDK (0.24) before adapting the example,
  because it is newer than the example. It found a 5-second default MCP timeout
  (raised to 30) and tracing that uploads conversations to OpenAI by default
  (now off unless `AGENT_TRACING_ENABLED=true`).
- Built the layers (routers → services → models), an `Agent` interface with
  `OpenAIAgent` and `FakeAgent`, Alembic migrations, a rate limiter, and error
  handlers that match the contract's `Error` schema.
- Wrote 29 unit tests and 16 integration tests. The integration tests check
  every response against `openapi.yaml`.

**Problems the AI caught and fixed during the work:**
- Settings read `OPENAI_API_KEY` from `.env` but the SDK reads the process
  environment, so the key is now passed explicitly.
- httpx logs full URLs at INFO level, and the Alpha Vantage URL contains the
  API key, so httpx logging is lowered to WARNING. Agent errors log only the
  exception type.
- Two simultaneous adds of the same ticker would have returned 500, so the
  database IntegrityError is now turned into 409.
- A module-level `app = create_app()` meant importing the module read `.env`.
  It switched to uvicorn `--factory` mode.
- The first contract-coverage test relied on FastAPI internals that changed in
  this version. It now compares against FastAPI's generated OpenAPI instead.

**Verified:**
- `pytest`: 45 passed. `ruff check` and `ruff format --check`: clean.
- Mutation check: renaming one `operation_id` made the contract test fail with
  a clear diff. The change was reverted.
- Smoke test: ran `alembic upgrade head` and uvicorn, then used curl on health,
  sessions, messages, watchlist, and `/docs`.

**Not yet verified:**
- Integration tests against Postgres (Docker was not running; covered in
  Phase 5 and CI)
- The real `OpenAIAgent` against live OpenAI and Alpha Vantage (needs my keys)

**Reviewed by hand:** _TODO (me)._
