from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import admin, public
from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="The Daily Slop",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(public.router, prefix="/api")
    app.include_router(admin.router, prefix="/admin")

    # Local-mode image serving. Prod images are served from GCS+CDN at /images/*
    # by the load balancer, not by FastAPI.
    if settings.is_local:
        local_images_dir = Path(settings.images_local_dir)
        # Sandboxed envs (e.g. test collection) may not be able to write the
        # configured path; the storage layer mkdirs again on first save.
        with suppress(OSError):
            local_images_dir.mkdir(parents=True, exist_ok=True)
        app.mount(
            "/images",
            StaticFiles(directory=str(local_images_dir), check_dir=False),
            name="images",
        )

    @app.get("/healthz", tags=["meta"])
    def healthz() -> dict[str, str]:
        return {"status": "ok", "version": app.version}

    return app


app = create_app()
