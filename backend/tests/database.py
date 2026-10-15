from pathlib import Path

from alembic.config import Config
from sqlalchemy import Connection

BACKEND_DIR = Path(__file__).resolve().parents[1]
POSTGRES_IMAGE = "postgres:17-alpine"  # та же версия, что в docker-compose.yml


def alembic_config(connection: Connection) -> Config:
    """Конфигурация Alembic, которая работает через уже открытое соединение теста."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["connection"] = connection
    return config
