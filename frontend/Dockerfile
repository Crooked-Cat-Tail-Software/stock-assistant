# syntax=docker/dockerfile:1

# ---- build stage: compile the React app ----
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --ignore-scripts
COPY . .
RUN npm run build

# ---- runtime stage: static files served by nginx as a non-root user ----
FROM nginxinc/nginx-unprivileged:1.30-alpine
# Runtime settings substituted into the nginx config (see nginx/default.conf.template).
# Defaults suit Docker Compose; the hosting platform overrides them.
ENV BACKEND_URL=http://backend:8000 \
    INTERNAL_API_TOKEN="" \
    TRUSTED_PROXY_CIDR=127.0.0.1/32 \
    REAL_IP_HEADER=X-Forwarded-For \
    RENDER_GIT_COMMIT=local
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1
