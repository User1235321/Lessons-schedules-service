from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.cookies import RefreshCookie
from app.api.errors import install_error_handlers
from app.api.request_context import RequestContextMiddleware, get_request_id
from app.api.routers import (
    auth,
    constraints,
    groups,
    health,
    imports,
    jobs,
    optimization,
    projects,
    rooms,
    schedules,
    streams,
    subgroups,
    subjects,
    teachers,
    workloads,
)
from app.bootstrap.container import Container, build_container
from app.bootstrap.settings import Settings
from app.infrastructure.logging import configure_logging


def create_app(container: Container | None = None) -> FastAPI:
    container = container or build_container(Settings())
    configure_logging(container.settings.log_level, get_request_id)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            container.close()

    app = FastAPI(title="Lessons Schedules Service", lifespan=lifespan)
    app.add_middleware(RequestContextMiddleware)
    app.state.container = container
    app.state.refresh_cookie = RefreshCookie(secure=container.settings.refresh_cookie_secure)
    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(projects.router)
    app.include_router(subjects.router)
    app.include_router(teachers.router)
    app.include_router(groups.router)
    app.include_router(subgroups.router)
    app.include_router(rooms.router)
    app.include_router(streams.router)
    app.include_router(workloads.router)
    app.include_router(constraints.router)
    app.include_router(optimization.router)
    app.include_router(jobs.router)
    app.include_router(schedules.router)
    app.include_router(imports.router)
    return app
