# Deployment

Production runs on **Render** (two free Docker web services, defined in
`render.yaml`) with the database on **Neon** (free Postgres that doesn't expire,
unlike Render's free Postgres, which is deleted after 30 days).

```
browser ──HTTPS──▶ stock-assistant-web (nginx: React app + /api proxy)
                          │  adds X-Internal-Token
                          ▼  HTTPS (public URL; free services can't use the private network)
                   stock-assistant-api (FastAPI) ──TLS──▶ Neon Postgres
                          │
                          └─▶ OpenAI + Alpha Vantage MCP
```

## How a change reaches production (CD)

1. Push to `main`, or merge a pull request.
2. GitHub Actions runs every CI job: contract, backend (including Postgres),
   frontend, end-to-end, and Docker smoke test.
3. **Only if all of them pass**, the `deploy` job:
   - triggers the backend's Render deploy hook, then waits until
     `/api/health` reports this commit (`RENDER_GIT_COMMIT`);
   - triggers the frontend's deploy hook, then waits until `/version` reports
     this commit;
   - smoke-tests production: health through the frontend, the session list, the
     security headers, and that the backend **refuses direct requests (403)**.

Render's own auto-deploy is off (`autoDeployTrigger: off`), so untested code
never reaches production. A deploy that fails or doesn't come up within 15
minutes fails the pipeline.

## Security model

- Secrets live only in Render's environment settings and GitHub Actions
  secrets. Values marked `sync: false` in `render.yaml` are never committed.
- **Shared secret between frontend and backend.** On Render the backend has a
  public URL, so without a check a client could skip nginx, fake
  `X-Forwarded-For`, and get around the rate limit. nginx sends
  `X-Internal-Token`, and the backend returns 403 to any `/api/*` request
  (except health) without it.
- The rate limit (10 questions per minute per client IP) caps OpenAI spend.
  Set `AGENT_MODE=fake` on the API service to run at no cost.

## One-time setup

### 1. Neon database

1. Create a free account at https://neon.tech and a project in **AWS US West 2
   (Oregon)**, the same area as the Render services.
2. Copy the connection string (Dashboard → Connect). It looks like
   `postgresql://user:password@ep-xxx.us-west-2.aws.neon.tech/neondb?sslmode=require`.
   The backend applies its migrations on startup, so no schema setup is needed.

### 2. Render services

1. Generate the shared secret, keep it for step 3, and don't commit it:
   ```bash
   openssl rand -hex 32
   ```
2. In Render: **New → Blueprint**, connect the GitHub repo, and select
   `render.yaml`. Render asks for the `sync: false` values:
   - `DATABASE_URL`: the Neon connection string
   - `OPENAI_API_KEY`, `ALPHAVANTAGE_API_KEY`: your keys
   - `INTERNAL_API_TOKEN`: the same generated value **on both services**
3. Wait for both services to build and become healthy. Note their URLs. Render
   adds a suffix when a name is taken. Ours is
   `https://stock-assistant-api-duq5.onrender.com`. `BACKEND_URL` on
   `stock-assistant-web` **must** match the API's real URL, because nginx sends
   the internal token to that host. If it was ever wrong, rotate
   `INTERNAL_API_TOKEN` on both services.
4. For each service, go to **Settings → Deploy Hook** and copy the URL. It's a
   secret: anyone with it can trigger deploys.

### 3. Connect GitHub Actions

```bash
gh secret set RENDER_DEPLOY_HOOK_BACKEND     # paste the API's deploy hook
gh secret set RENDER_DEPLOY_HOOK_FRONTEND    # paste the web service's deploy hook
gh variable set BACKEND_URL --body "https://stock-assistant-api-duq5.onrender.com"
gh variable set FRONTEND_URL --body "https://stock-assistant-web.onrender.com"
gh variable set DEPLOY_ENABLED --body "true"
```

The next push to `main` deploys automatically once CI passes. To redeploy
without a code change, re-run the latest workflow run on `main` in the Actions
tab.

## Free tier behavior

- Each service **spins down after 15 minutes without traffic**. The first
  request afterwards takes about a minute, or longer if both services are
  asleep. Open the site once before a demo or review.
- 750 free instance hours per month are shared by both services. Sleeping
  services don't use any, so normal class use stays well within the limit.
- Neon's free tier suspends compute when idle and resumes on the first query,
  which the backend's `pool_pre_ping` handles.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Deploy job times out waiting for a commit | The Render dashboard deploy logs for that service (build errors, failing health check) |
| `/api/*` returns 403 through the website | `INTERNAL_API_TOKEN` differs between the two services |
| `/api/*` through the website shows another service's page ("Service Suspended") | `BACKEND_URL` points at someone else's Render service. Fix it, then rotate `INTERNAL_API_TOKEN` |
| Website loads but `/api` gives 502/504 | `BACKEND_URL` on the web service, and whether the API service is up |
| Health shows `"database": "unavailable"` | `DATABASE_URL` is correct and includes `?sslmode=require`, and the Neon project is active |
