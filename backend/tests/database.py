from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from alembic.config import Config
from sqlalchemy import Connection, event

BACKEND_DIR = Path(__file__).resolve().parents[1]
POSTGRES_IMAGE = "postgres:17-alpine"  # та же версия, что в docker-compose.yml


def alembic_config(connection: Connection) -> Config:
    """Конфигурация Alembic, которая работает через уже открытое соединение теста."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["connection"] = connection
    return config


@contextmanager
def recorded_statements(connection: Connection) -> Iterator[list[str]]:
    """Первые слова SQL-запросов, ушедших через connection внутри блока, например "UPDATE"."""
    statements: list[str] = []

    def record(*args: Any) -> None:
        statement = args[2]  # conn, cursor, statement, parameters, context, executemany
        statements.append(statement.split(maxsplit=1)[0])

    event.listen(connection, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(connection, "before_cursor_execute", record)
