"""Optional shared-token gate for Phase-1 cloud demos."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings

_OPEN_PREFIXES = (
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
)


class AccessTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        token = (settings.access_token or "").strip()
        if not token:
            return await call_next(request)

        # CORS preflight must pass without a token (middleware may sit outside CORS).
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if path == "/" or any(path == p or path.startswith(p + "/") for p in _OPEN_PREFIXES):
            return await call_next(request)

        # X-Axiom-Token only — Authorization: Bearer is reserved for user session JWT.
        provided = (request.headers.get("x-axiom-token") or "").strip()

        if provided != token:
            return JSONResponse(
                status_code=401,
                content={"detail": "需要有效的存取權杖（X-Axiom-Token）", "code": "unauthorized"},
            )
        return await call_next(request)
