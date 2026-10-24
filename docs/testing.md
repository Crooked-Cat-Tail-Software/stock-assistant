# Testing strategy

Four layers, from fastest and narrowest to slowest and broadest. Each catches
problems the others can't. No layer ever calls OpenAI, Alpha Vantage, or Yahoo: a
`FakeAgent` (backend) or an in-memory fake API (frontend unit tests) stands in,
so every test runs without keys or cost, and CI has no keys at all.

| Layer | Location | What it proves | Speed |
|-------|----------|----------------|-------|
| Backend unit | `backend/tests/unit/` | Business rules: titles, ordering, history, duplicates, the rate limiter, URL handling, and that the real agent's API key never reaches logs or errors | ~2 s |
| Backend integration | `backend/tests/integration/` | Real HTTP and a real database built by the real migrations. **Every response is validated against `openapi.yaml`**, and the implemented routes must match the contract exactly | ~1 s (SQLite) |
| Frontend unit | `frontend/src/**/*.test.ts(x)` | API client error handling, validation rules (checked against the contract), and UI flows driven like a user would (Testing Library) | ~3 s |
| End-to-end | `frontend/e2e/` | The whole stack in a real browser: production frontend build → proxy → FastAPI → database | ~15 s |

## Key workflows and where they're tested

| Workflow (from `product-spec.md`) | Integration | Frontend unit | E2E |
|---|:-:|:-:|:-:|
| F1 Ask a question; see answer and data sources | ✓ | ✓ | ✓ |
| F1 Follow-ups use earlier turns as context | ✓ | ✓ | ✓ |
| F2 Conversations persist (reload / restart) | ✓ | ✓ | ✓ |
| F3 Delete a conversation | ✓ | ✓ | ✓ |
| F4 Watchlist add / list / remove, uppercase, 409 on duplicate | ✓ | ✓ | ✓ |
| F5 Ask about a watchlist ticker (prefilled, not auto-sent) | n/a | ✓ | ✓ |
| F6 Health check, including 503 when the database is down | ✓ | ✓ | (used as readiness check) |
| Agent failure → 502, nothing saved, question kept in the UI | ✓ | ✓ | ✓ |
| Guardrails: 2,000-char limit, rate limit (429) | ✓ | ✓ | |

## Running the tests

```bash
# Backend
cd backend
uv run pytest tests/unit
uv run pytest tests/integration                         # SQLite (default)
TEST_DATABASE_URL=postgresql://app:app@localhost:5432/app_test \
  uv run pytest tests/integration                       # Postgres, as CI does
uv run pytest --cov                                     # with coverage

# Frontend
cd frontend
npm test                # unit tests
npm run coverage        # with coverage (HTML report in frontend/coverage/)
npx playwright install chromium   # once
npm run e2e             # end-to-end; starts its own servers on ports 8001/4173
```

## Coverage (2026-10-15)

- Backend: 97% of statements, including branches. Not covered: the real
  agent's startup path, which needs live keys.
- Frontend unit tests: 93% of statements and 88% of branches.

## Continuous integration

`.github/workflows/ci.yml` runs on every push to `main` and every pull request:

1. **API contract:** validates `openapi.yaml` and fails if the generated
   frontend types are stale.
2. **Backend:** ruff lint and format, unit tests, then integration tests
   against a **Postgres 17** service container (production uses Postgres;
   local runs default to SQLite).
3. **Frontend:** lint (including the "no `fetch` outside `client.ts`" rule),
   typecheck, unit tests with coverage, and the production build.
4. **End-to-end:** runs after jobs 2 and 3 pass, and uploads the Playwright
   report if it fails.
5. **Docker Compose:** builds both images, starts the full stack, waits for
   every health check, then smoke-tests through nginx (health, security
   header, one chat turn).

6. **Production image:** builds the root `Dockerfile` (nginx + API in one
   container, which is what Render runs), then smoke-tests it: page,
   `/version`, health with commit, CSP, a chat turn, and the API bound to
   loopback only.

Render deploys only commits on which all six pass. After a deploy,
`.github/workflows/verify-deploy.yml` smoke-tests the live site (see
`docs/deployment.md`).

## Writing new tests

- New endpoint: add an integration test that calls `assert_conforms(...)` on
  every response (see `tests/integration/contract.py`).
- Need the agent to behave differently: pass a small class with an async
  `reply()` method to `make_client(agent=...)`. Include `__fail__` in a
  question to make `FakeAgent` raise.
- Frontend: render with `<ApiProvider api={createFakeApi()}>` and override
  single methods with `vi.mocked(api.x).mockRejectedValueOnce(...)`.
- Before trusting a new test, break the code it guards and check that the test
  fails.
