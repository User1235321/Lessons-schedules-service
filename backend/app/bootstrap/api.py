from fastapi import FastAPI

from app.api.errors import install_error_handlers
from app.api.routers import health
from app.bootstrap.container import Container, build_container
from app.bootstrap.settings import Settings


def create_app(container: Container | None = None) -> FastAPI:
    app = FastAPI(title="Lessons Schedules Service")
    app.state.container = container or build_container(Settings())
    install_error_handlers(app)
    app.include_router(health.router)
    return app
