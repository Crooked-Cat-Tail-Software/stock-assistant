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

### 2026-10-15 — Phase 5: containerization

**Asked:** Run the full system with Docker Compose.

**AI did:**
- Wrote multi-stage Dockerfiles that run as non-root users:
  - Backend: Python 3.13-slim with uv 0.13.1 pinned and locked installs. The
    runtime image has no uv or compilers.
  - Frontend: a Node 24 build stage, then unprivileged nginx 1.30.
- Wrote `docker-compose.yml` (Postgres 17, backend, frontend) with health
  checks, a named volume, and the backend unpublished.
- The nginx config proxies `/api`, sets security headers (CSP and others),
  caches hashed assets, and serves the SPA fallback. It overwrites
  `X-Forwarded-For` so clients can't spoof their IP past the rate limit.
- Added a separate `app_test` database (created by an init script) so
  integration tests can't wipe dev data.
- Added a CI job that builds the images, starts the stack, and smoke-tests it
  through nginx.

**Verified:**
- `docker compose build` and `up --wait`: all 3 services healthy, and
  migrations ran on Postgres.
- curl checks: health through nginx, security headers on pages and assets,
  SPA deep-link fallback, unknown API routes return JSON errors, and the
  backend port is not published.
- IP spoofing: a request with `X-Forwarded-For: 6.6.6.6` was not seen as
  6.6.6.6. A request from inside the network showed the real client IP.
  (Requests from the Mac host appear to nginx as `151.101.0.223`, an artifact
  of Docker Desktop's port forwarding on this machine, not of the app.)
- Containers run as uid 10001 (backend) and nginx (frontend). The image
  contains no tests or `.env`.
- **First run of the integration tests on Postgres: 19 passed.**
- Dev data survived both a test run and a `docker compose down` / `up`.
- Browser on :8080: chat works, and the console is empty (no CSP violations).
- The CI smoke-test commands passed against the local stack, and `actionlint`
  is OK.

**Reviewed by hand:** _TODO (me)._

### 2026-10-15 — Phase 6: CI/CD

**Asked:** Deploy automatically when tests pass.

**Research before building:** read Render's current Blueprint spec and
free-tier docs instead of relying on memory. Three findings changed the design:
- Free Render Postgres is deleted after 30 days (+14 days grace), which could
  fall inside the peer-review window. **My decision:** use Neon's free Postgres,
  which doesn't expire.
- Free services can't receive private-network traffic, so nginx must call the
  API's public HTTPS URL. The proxy now sends `Host $proxy_host` and SNI; the
  old `Host $host` would have broken Render's routing.
- That makes the backend publicly reachable, so a client could bypass nginx
  and spoof `X-Forwarded-For` to avoid the rate limit. Added a shared-secret
  `X-Internal-Token` check (constant-time compare, 403, health exempt),
  documented in the contract.

**AI did:**
- Wrote `render.yaml` (two Docker web services, free plan, auto-deploy off,
  secrets as `sync: false`).
- Health now reports `commit` (from `RENDER_GIT_COMMIT`), and the frontend
  serves `/version`.
- Added a `deploy` job: it runs only on `main` after all 5 CI jobs pass,
  deploys the backend and then the frontend, waits for each to report the
  tested commit, and smoke-tests production (including that the backend
  returns 403 to direct requests).
- Runs on `main` are no longer cancelled by newer pushes, so a deploy can't be
  interrupted halfway.
- Wrote `docs/deployment.md`.

**My decisions:** Neon for the database. A public GitHub repo. Commits keep my
email as author (I was told it becomes public).

**Verified:**
- Backend: 60 passed (4 new deployment-config tests). Frontend: 36 passed.
  E2E: 5 passed. Typecheck, lint, and ruff are clean. `actionlint` OK.
- Rehearsed the Render configuration locally with a token in Compose: the app
  works through nginx (200), direct backend requests get 403, health stays
  open, `/version` works, and spoofed XFF is still ignored.
- The `wait-for-commit.sh` script both succeeds and times out correctly.

**Not yet verified:**
- Render's actual client-IP header behavior, and the live deploy (Phase 7)

**Reviewed by hand:** _TODO (me)._

### 2026-10-15 → 10-19 — Publishing and first deployment (Phase 6 follow-up / Phase 7)

**First CI run on GitHub failed.** `astral-sh/setup-uv@v10` doesn't exist: that
project publishes only exact version tags. I had checked the latest *release*
but assumed a major-version tag existed. Fixed by pinning **every** action to
its release commit SHA (version in a comment), which is GitHub's
supply-chain-hardening recommendation. The second run was green: 37 unit +
23 Postgres integration tests, 5 e2e tests, and the Docker smoke test.

**Render setup (done by me in the dashboard):** connected Render's GitHub app to
this repo only (least privilege), created the Blueprint, and entered secrets
directly in Render and GitHub. None went through the AI chat.

**Problem found during verification:** Render named the API
`stock-assistant-api-duq5` because the plain name belongs to another account.
`render.yaml` had the guessed URL, so nginx forwarded `/api`, and with it the
internal token, to that unrelated, suspended service. Editing the value in the
dashboard didn't stick, because a Blueprint sync reapplied the wrong value from
`render.yaml`. Fixed at the source by correcting `render.yaml`. Because the
token had been sent to another host, it is being rotated. The AI found the
real URLs through Render's deployment statuses on GitHub
(`gh api .../deployments`), without needing dashboard access.

**Lesson:** the platform-assigned URL should be read back after creation,
never assumed. `docs/deployment.md` now says so.

**Verified live:**
- Backend health `ok` with Neon connected and the deployed commit reported
- Direct backend requests return 403
- Website `/api/*` returns 200 once both services share the token
- Both deploy-hook secrets present (names only)

**Reviewed by hand:** _TODO (me)._

### 2026-10-19 — Deploy hooks replaced by Render's `checksPass`

**What happened:** the deploy job failed three times because both deploy-hook
secrets held a 64-character `openssl` token instead of Render's hook URL. The
two values are easy to confuse: one is *generated*, the other is *copied* from
Render. Each fix made the failure clearer:
1. curl reported `Could not resolve host: ***`.
2. A format check reported "not a deploy hook URL, 64 characters".
3. Non-revealing yes/no diagnostics showed "only 0-9 and a-f: yes, no
   https://, no ?key=", which confirmed the value was a token and the check
   was not over-strict.

While writing the diagnostics, the AI first used `eval` (flagged by
shellcheck), then `[[ ]]; $?`, which would have aborted under GitHub's
`bash -e`. Testing exactly as GitHub runs it (`bash -e`) caught this before
pushing. The final version uses `case` patterns.

**My decision:** remove deploy hooks entirely. Render now deploys only after
all GitHub checks pass (`autoDeployTrigger: checksPass`), so there are no
deploy secrets in GitHub at all.

**Design point the AI caught:** with `checksPass`, a verification job inside CI
would deadlock: Render would wait for the job while the job waited for Render.
Verification moved to `verify-deploy.yml`, triggered by Render's
`deployment_status` event after a successful web deploy.

**Trade-off accepted:** the two services now deploy independently rather than
backend-first, so the API must stay backward compatible for one deploy.

**Reviewed by hand:** _TODO (me)._

### 2026-10-20 — Production verification found two deployment issues

**Rate limit didn't work on Render.** I verified it without any API cost by
posting to a nonexistent session: the limit is checked before the session
lookup, so each request counts but never calls OpenAI. 12 of 12 requests got
through. A temporary `/__whoami` page (showing the caller only their own
address data) revealed Render's chain: Cloudflare → changing 10.x Render
node → 127.0.0.1 proxy → nginx. My Phase 6 config took the last
`X-Forwarded-For` entry, which changes almost every request. That assumption
had been explicitly marked "verify in Phase 7", and verification caught it.

**Fix:** trust only the 127.0.0.1 proxy and only Cloudflare's
`CF-Connecting-IP`. A client-sent `CF-Connecting-IP` was rejected by
Cloudflare with 403, so it can't be forged. I checked uvicorn 0.54's
proxy-header source to confirm the backend takes the leftmost XFF entry,
which nginx sets. I tested both modes locally (Compose, and the image with
Render's settings) before pushing.

**Result in production:** 10 requests allowed, then 429 with `Retry-After`.
Fake `X-Forwarded-For`, `X-Real-IP`, and `True-Client-IP` headers don't get
around it.

**Second finding — CI gate gap:** the commit that changed `render.yaml`
deployed 1 second after the push, while CI was still running. Commits that
don't touch `render.yaml` deployed 3 seconds after CI passed. Render's
Blueprint auto-sync applies config changes immediately. Documented in
`docs/deployment.md` with two mitigations. The cleanup commit (removing
`/__whoami`) deliberately leaves `render.yaml` untouched to confirm that
normal commits stay gated.

**Reviewed by hand:** _TODO (me)._

### 2026-10-23 — Course criteria changed; re-planned to the new rubric

**What happened:** before starting the planned Phase 8 (agent extension pack
and security artifacts), the AI re-read the course requirements to match their
exact wording. It found they had been **revised on 2026-10-16**: 12 criteria,
24 points, 10 to pass. The API contract, extension pack, and security criteria
were gone. Product specification (with a public task tracker), agent team,
context management, observability, alerting, and an on-call agent were new.
It stopped, re-scored the project against the new criteria (about 14–17/24),
and presented options with their cost.

**My decision:** do only the quick wins (single test command, agent team,
modular context docs, public task tracker). I skipped observability, the
on-call agent, and the dev/prod split for now.

**AI did:**
- Created the public tracker (GitHub Issues #1–#13) with labels. Issues for
  this phase's work (#1–#4) were created **before** the work, with acceptance
  criteria. The agent posted its plan on each issue before starting and
  referenced them in commits. Earlier work was recorded as closed issues
  (#5–#13) labeled `recorded-after-the-fact`, each linking the commits and
  tests that deliver it.
- `make test` (verified: a deliberately broken test gives exit 2).
- `docs/agent-team.md` and four subagents in `.claude/agents/`, with tool
  lists matching each role (reviewers are read-only).
- `docs/process.md`, and AGENTS.md rewritten as an entry point. It was also
  inaccurate: it still listed `mcp-server/` and docs that were never built.
- `ops/scripts/check-links.py`, in `make lint` and CI. It was shown to catch a
  missing file and a bad `#anchor`, and to accept a real anchor with tricky
  characters.

**Slip caught:** the first batch of issue-creation commands passed two
`--label` flags as one argument (zsh doesn't split variables), so nothing was
created, yet the script printed "closed". The AI checked the tracker, confirmed
nothing half-created existed, and redid it with a guard that refuses to close
an issue without a real issue number.

**Reviewed by hand:** _TODO (me)._

### 2026-10-24 — Phase 9: README and architecture (issue #4)

**Asked:** Final documentation pass.

**AI did:**
- Posted its plan on #4, then rewrote the README. The problem, features, and
  expected behavior come first, then the live URL, a CI badge, and a
  screenshot of the **live** site. The screenshot was captured with Playwright
  by opening an existing conversation, so no OpenAI cost and no data changes.
- Two Mermaid diagrams (system architecture, CI/CD gate), a component table,
  and a "How it was built" section.
- A course-criteria table that is **honest about gaps**: observability is
  partial (logs only), and alerting and the on-call agent are not implemented.
- Replaced a Render rollback instruction ("Manual Deploy → Deploy a previous
  commit") that the AI could not confirm matched Render's UI with a
  revert-based rollback that goes through the CI gate.

**Verified:**
- In a **fresh clone from GitHub**: `make install` and `make test` (96 tests
  pass), and the "without Docker" backend steps (migration creates
  `backend/dev.db`, health `ok`, `/docs` 200).
- `docker compose up --build` from a clean checkout is covered by CI's Docker
  job, which passed on merge commit `d955d13`. Docker wasn't running locally
  at the time.
- `check-links.py`: 0 broken links, including the README's new `#section`
  anchors.

**Reviewed by hand:** _TODO (me)._
