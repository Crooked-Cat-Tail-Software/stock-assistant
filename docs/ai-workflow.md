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

### 2026-10-15 — Phase 3: frontend

**Asked:** Build the React frontend.

**AI did:**
- Set up React 19, Vite 8, and TypeScript with types generated from
  `openapi.yaml` (`npm run gen:api`). All backend calls live in
  `src/api/client.ts`, and an ESLint rule fails the build on any other `fetch`.
- Built the chat view (Markdown replies, data-source chips, pending and error
  states), the session list, the watchlist (with "Ask about"), and a health
  badge.
- Wrote 35 Vitest and Testing Library tests against an in-memory fake API,
  including a check that the client-side validation rules match the contract.

**Problems found and fixed:**
- **Contract bug:** the backend can return `"arguments": null` for a tool
  call, but the contract didn't allow null. Fixed the contract first, then
  added a backend test, and confirmed that test fails against the old contract.
- **Dependency conflict:** the newest TypeScript was too new for both
  `typescript-eslint` and `openapi-typescript`. Pinned TypeScript 5.9, which
  satisfies both, instead of forcing the install.
- **State bug caught in review:** reopening a chat after switching away could
  show the wrong messages. Replaced the bookkeeping with a React `key` per
  opened chat.
- **Lint:** the new React rule `set-state-in-effect` flagged one hook, which
  was restructured.
- **Tests:** added Testing Library cleanup (it doesn't auto-run without
  Vitest globals). Gave the watchlist button the accessible name "Ask about
  TSLA", which also fixes a screen-reader ambiguity.
- The contract-sync test reads `openapi.yaml` with Node rather than loosening
  Vite's file-serving restriction.

**Verified:**
- `npm test`: 35 passed. `typecheck`, `lint`, and `build` are clean. Backend
  `pytest`: 46 passed.
- The lint guardrail fails on a temporary `fetch` in a component (file removed
  afterwards).
- Manual browser check against the real backend (fake agent): asked an example
  question, added `nvda` (stored as NVDA), used Ask about NVDA, and reopened the
  first conversation. At 375 px there's no horizontal scroll, and the console
  shows no errors.

**Reviewed by hand:** _TODO (me)._

### 2026-10-15 — Phase 4: testing and CI

**Asked:** Complete the testing layer.

**AI did:**
- Added coverage reporting for both sides and wrote tests for the gaps:
  - The real agent's run and error path, with `Runner.run` replaced
  - A check that the API key never appears in logs or errors
  - Health returning 503 when the database is down
  - The duplicate-watchlist race
  - Postgres URL handling
  - Session-list load failures in the UI
- Added 5 Playwright end-to-end tests covering features F1–F5 and the failure
  path, against the production frontend build and the real backend.
- Wrote `.github/workflows/ci.yml` (contract, backend on Postgres 17,
  frontend, and e2e) and `docs/testing.md`.

**Problem found by the new tests:** the API-key-leak test passed when run on
its own but failed in the full suite. Its secret-not-in-logs assertion had been
passing vacuously, because nothing was logged at all. The cause was Alembic's
`fileConfig`, which disables all existing loggers by default, so running
migrations in-process (as the integration tests do) silenced the app's error
logs. Fixed with `disable_existing_loggers=False` in `migrations/env.py`. The
extra assertion that the error type *is* logged is what exposed this.

**Also:** looked up the latest versions of the GitHub Actions used
(checkout v7, setup-node v7, setup-uv v10, upload-artifact v7) instead of
writing them from memory, since all were several major versions newer.

**Verified:**
- Backend: 56 passed, 97% coverage, ruff clean.
- Frontend: 36 passed, 93% statement coverage. Typecheck and lint are clean.
- E2E: 5 passed.
- `actionlint` reports the workflow as valid. CI's commands ran locally:
  `uv sync --locked`, `npm ci`, the OpenAPI validation, and the stale-types
  check.

**Not yet verified:**
- The workflow running on GitHub (the repo has no remote yet)
- Integration tests on Postgres (Docker isn't running locally; CI will be the
  first Postgres run)

**Reviewed by hand:** _TODO (me)._
