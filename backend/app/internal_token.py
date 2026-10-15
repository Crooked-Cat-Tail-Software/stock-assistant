"""Reject requests that didn't come through the frontend's nginx.

On Render, free web services can't use the private network, so the backend has
a public URL. Without this check, a client could call it directly, set its own
X-Forwarded-For, and get around the per-IP rate limit. nginx adds the shared
secret; anything without it gets 403.
"""

import hmac

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

HEADER = "X-Internal-Token"
# Health stays open so the platform and CI can check the deployment.
OPEN_PATHS = {"/api/health"}


def install_internal_token_check(app: FastAPI, token: str) -> None:
    expected = token.encode()

    @app.middleware("http")
    async def _require_internal_token(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/") and path not in OPEN_PATHS:
            supplied = request.headers.get(HEADER, "").encode()
            # Constant-time comparison so the token can't be guessed byte by byte.
            if not hmac.compare_digest(supplied, expected):
                return JSONResponse(
                    {"code": "forbidden", "message": "Requests must come through the web app."},
                    status_code=403,
                )
        return await call_next(request)
