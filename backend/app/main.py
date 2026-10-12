"""Axiom FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.errors import AxiomError
from app.providers import ProviderError
from app.vision import VisionError
from app.dependencies import AppContainer
from app.middleware_access import AccessTokenMiddleware
from app.routers import router
from app.services.seed import init_db


def _cors_origins() -> list[str]:
    defaults = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]
    extra = [o.strip() for o in (settings.cors_origins or "").split(",") if o.strip()]
    # Preserve order, drop dupes
    seen: set[str] = set()
    out: list[str] = []
    for origin in defaults + extra:
        if origin not in seen:
            seen.add(origin)
            out.append(origin)
    return out


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    app.state.container = AppContainer()
    try:
        yield
    finally:
        await app.state.container.close()


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)


@app.exception_handler(AxiomError)
async def handle_axiom_error(_: Request, exc: AxiomError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code},
    )


@app.exception_handler(ProviderError)
async def handle_provider_error(_: Request, exc: ProviderError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": exc.message, "code": exc.code})


@app.exception_handler(VisionError)
async def handle_vision_error(_: Request, exc: VisionError) -> JSONResponse:
    status = 400 if exc.code == "invalid_image" else 503
    return JSONResponse(status_code=status, content={"detail": exc.message, "code": exc.code})


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AccessTokenMiddleware)

app.include_router(router)
