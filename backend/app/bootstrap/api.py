from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.cookies import RefreshCookie
from app.api.errors import install_error_handlers
from app.api.routers import auth, health, jobs
from app.bootstrap.container import Container, build_container
from app.bootstrap.settings import Settings


def create_app(container: Container | None = None) -> FastAPI:
    container = container or build_container(Settings())

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            container.close()

    app = FastAPI(title="Lessons Schedules Service", lifespan=lifespan)
    app.state.container = container
    app.state.refresh_cookie = RefreshCookie(secure=container.settings.refresh_cookie_secure)
    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(jobs.router)
    return app
