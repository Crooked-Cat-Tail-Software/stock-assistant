# syntax=docker/dockerfile:1
#
# Production image: frontend (nginx) and backend (FastAPI) in ONE container, so
# ONE Render service. With two free Render services, the API slept after 15
# idle minutes and requests from the web service got a 502 instead of waking
# it (issue #24). One service means a visitor's request wakes everything.
#
# Local development still uses docker-compose.yml (separate containers).

# ---- 1. build the React app ----
FROM node:24-alpine AS frontend
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --ignore-scripts
COPY frontend/ ./
RUN npm run build

# ---- 2. install backend dependencies (locked) ----
FROM python:3.13-slim AS backend
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project
COPY backend/app ./app
COPY backend/migrations ./migrations
COPY backend/alembic.ini ./

# ---- 3. runtime: nginx + uvicorn, non-root ----
FROM python:3.13-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx-light gettext-base \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=backend --chown=app:app /app /app
COPY --from=frontend /app/dist /usr/share/nginx/html
COPY frontend/nginx/default.conf.template /etc/stock-assistant/site.conf.template
COPY ops/single-service/nginx.conf /etc/stock-assistant/nginx.conf
COPY --chmod=755 ops/single-service/start.sh /usr/local/bin/start-stock-assistant

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    # nginx → backend on loopback; nothing else can reach the backend.
    BACKEND_URL=http://127.0.0.1:8000 \
    INTERNAL_API_TOKEN="" \
    TRUSTED_PROXY_CIDR=127.0.0.1/32 \
    REAL_IP_HEADER=X-Forwarded-For \
    RENDER_GIT_COMMIT=local \
    DATABASE_URL=sqlite:////tmp/stock-assistant.db
USER app
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=2)"
CMD ["start-stock-assistant"]
