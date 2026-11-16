from fastapi import FastAPI

from app.api.cookies import RefreshCookie
from app.api.errors import install_error_handlers
from app.api.routers import (
    auth,
    groups,
    health,
    projects,
    rooms,
    streams,
    subgroups,
    subjects,
    teachers,
    workloads,
)
from app.bootstrap.container import Container, build_container
from app.bootstrap.settings import Settings


def create_app(container: Container | None = None) -> FastAPI:
    app = FastAPI(title="Lessons Schedules Service")
    app.state.container = container = container or build_container(Settings())
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
    return app
