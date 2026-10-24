# Deployment

Production runs as **one free Docker web service on Render**
(`stock-assistant-web`, defined in `render.yaml`, built from the root
`Dockerfile`), with the database on **Neon** (free Postgres that doesn't expire,
unlike Render's free Postgres, which is deleted after 30 days).

```
browser ──HTTPS (Cloudflare)──▶ stock-assistant-web  ── one container ─────────────────────┐
                                │  nginx :8080  (React app, security headers, client IP) │
                                │     │ /api/*                                            │
                                │     ▼                                                   │
                                │  FastAPI 127.0.0.1:8000 (not reachable from outside)    │
                                └─────┬────────────────────────────────────────────────────┘
                                      ├──TLS──▶ Neon Postgres
                                      └──▶ OpenAI · Yahoo Finance (yfinance, RSS) · Alpha Vantage MCP
```

Local development uses the same nginx config and backend, but as separate
containers in `docker-compose.yml`.

## Why one service (issue #24)

The first production setup had two Render services, web and API. Render's free
plan sleeps a service after 15 idle minutes, and testing showed that **a request
from the web service to the sleeping API gets an immediate 502 instead of waking
it**: 12 of 12 requests through the site failed over 2 minutes, until one
direct request woke the API (51 s). Visitors never call the API directly, so
the site stayed broken after every idle period.

With one service, the visitor's own request wakes the container. The start
script ([`ops/single-service/start.sh`](../ops/single-service/start.sh)) runs
migrations, starts the API on loopback, and **starts nginx only once the API
answers**. Render holds the waking request until the port opens, so it gets a
real answer, not a 502. A local cold-start test polled every 0.2 s from
t = 0 and saw only "not listening yet" and then 200, never 502. If either
process dies, the container exits and Render restarts it.

Side benefits: no cross-service hop, no shared secret, the API isn't publicly
reachable, and half the free instance hours.

## How a change reaches production (CD)

1. Push to `main`, or merge a pull request.
2. GitHub Actions runs every CI check (`.github/workflows/ci.yml`): contract,
   backend (including Postgres), frontend, end-to-end, the Compose smoke test,
   and the **production image** smoke test (the root `Dockerfile`).
3. **Render deploys the commit only if all of those checks pass**
   (`autoDeployTrigger: checksPass`). If any check fails, production keeps
   running the previous version.
4. Render reports the deploy back to GitHub. When it succeeds,
   `.github/workflows/verify-deploy.yml` waits until `/version` and
   `/api/health` both report the deployed commit, then smoke-tests health, the
   session list, and the security headers.

Verification is a separate workflow on purpose. With `checksPass`, Render waits
for every check on a commit. A verification job inside CI would wait for
Render while Render waited for it, so nothing would deploy.

**Rollback:** revert the bad commit on `main`. The revert goes through the same
gate. In an emergency, Render's dashboard can redeploy an earlier successful
deploy directly.

## Security model

- Secrets live only in Render's environment settings. Values marked
  `sync: false` in `render.yaml` are never committed, and GitHub stores no
  deploy secrets.
- **The API isn't reachable from outside.** It listens on 127.0.0.1 inside the
  container, and only nginx talks to it (CI checks it isn't bound to any other
  address). uvicorn trusts forwarded client-IP headers only from 127.0.0.1.
  The `X-Internal-Token` check still exists in the code for setups where the
  API has its own public URL, but it isn't needed here.
- **Outside data is untrusted.** The agent reads news headlines and summaries
  written by third parties. The feed is size-capped, parsed with `defusedxml`
  (no DTDs or entities), and only https links are passed on. The agent is
  instructed never to follow instructions found in tool results. Its tools are
  read-only, which limits what a prompt-injection attempt could do.
- **Rate limit (10 questions per minute per visitor)** caps OpenAI spend. Set
  `AGENT_MODE=fake` on the service to run at no cost.

### How the visitor's IP is found (verified on Render, 2026-10-20)

The rate limit is only as good as the client IP it counts by. On Render a
request travels:

```
visitor → Cloudflare edge (changes) → Render node 10.x (changes) → local proxy 127.0.0.1 → nginx
X-Forwarded-For: "<anything the client sent>,<visitor>, <cloudflare edge>, <render node>"
CF-Connecting-IP: "<visitor>"   (set by Cloudflare; a client-sent value is rejected with 403)
```

- Taking the last `X-Forwarded-For` entry (the first design) gave a different
  10.x address almost every request, so the limit **never triggered**.
  Production testing found this: 12 of 12 requests got through.
- nginx trusts only the local proxy (`TRUSTED_PROXY_CIDR=127.0.0.1/32`) and
  only `CF-Connecting-IP` (`REAL_IP_HEADER`). It then overwrites
  `X-Forwarded-For` with that single address for the API.
- Verified in production: the 11th request within a minute gets 429 with
  `Retry-After`, and fake `X-Forwarded-For`, `X-Real-IP`, or `True-Client-IP`
  headers don't get around it.
- Compose and the CI image keep `REAL_IP_HEADER=X-Forwarded-For` with nothing
  trusted, so nginx uses the direct peer address.

### Known gap: `render.yaml` changes skip the CI gate

Render's Blueprint **auto-sync** applies a changed `render.yaml` immediately
and redeploys the affected services, **without waiting for CI** (observed for
commit `001e12a`, which deployed 1 second after the push). Ordinary code
commits are still gated. Two ways to handle it:

1. Turn off auto-sync in Render (Blueprint → Settings), and sync manually
   after CI passes. This is stricter, and is the recommended option.
2. Keep auto-sync, but commit `render.yaml` changes on their own, never
   together with code changes, and only after the code they rely on is already
   live.

## One-time setup

### 1. Neon database

1. Create a free account at https://neon.tech and a project in **AWS US West 2
   (Oregon)**, the same area as the Render service.
2. Copy the connection string (Dashboard → Connect). It looks like
   `postgresql://user:password@ep-xxx.us-west-2.aws.neon.tech/neondb?sslmode=require`.
   The backend applies its migrations on startup, so no schema setup is needed.

### 2. Render service

1. In Render: **New → Blueprint**, connect the GitHub repo, and select
   `render.yaml`. Render asks for the `sync: false` values: `DATABASE_URL`
   (the Neon connection string), `OPENAI_API_KEY`, and `ALPHAVANTAGE_API_KEY`.
2. Wait for the service to build and become healthy. Its health check is
   `/api/health`, which covers both nginx and the API.
3. Check that **Settings → Auto-Deploy** shows "After CI checks pass". The
   Blueprint sets this.

### 3. Tell GitHub where production is

The verify workflow needs the public URL (not a secret):

```bash
gh variable set FRONTEND_URL --body "https://stock-assistant-web.onrender.com"
```

Leave `BACKEND_URL` unset. Setting it switches the verify workflow to the old
two-service checks. To redeploy without a code change, use **Manual Deploy →
Deploy latest commit** in Render.

## Free tier behavior

- The service **sleeps after 15 minutes without traffic**. The first visit
  afterwards takes about a minute while Render starts the container (Render
  shows its own loading page). After that, the site is fast. Open it once
  before a demo or review.
- 750 free instance hours per month. A sleeping service uses none, and one
  service always on would use at most about 744.
- Neon's free tier suspends compute when idle and resumes on the first query,
  which the backend's `pool_pre_ping` handles.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Checks passed but nothing deployed | `autoDeployTrigger` is `checksPass` (Render → service → Settings → Auto-Deploy), and the Render GitHub app can see this repo |
| Verify workflow times out waiting for a commit | The Render deploy logs (build errors, failing health check) |
| Site loads but `/api` gives 502 | Render logs: did the start script report "API did not become ready" or "a process exited"? Usually a bad `DATABASE_URL` or a missing key |
| Health shows `"database": "unavailable"` | `DATABASE_URL` is correct and includes `?sslmode=require`, and the Neon project is active |
| "The assistant's data service failed" | A 502/503/504 that came from Render or nginx, not the app. Check the Render service's Events for restarts or out-of-memory errors |
