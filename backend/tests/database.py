import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from alembic.config import Config
from sqlalchemy import Connection, Engine, event, text

BACKEND_DIR = Path(__file__).resolve().parents[1]
POSTGRES_IMAGE = "postgres:17-alpine"  # та же версия, что в docker-compose.yml


def wait_for_lock_waiters(engine: Engine, count: int, timeout: float = 10) -> None:
    query = text(
        "SELECT count(*) FROM pg_stat_activity"
        " WHERE wait_event_type = 'Lock' AND datname = current_database()"
    )
    deadline = time.monotonic() + timeout
    with engine.connect() as connection:
        while time.monotonic() < deadline:
            waiting = connection.scalar(query)
            # pg_stat_activity запоминается до конца транзакции, свежие данные — в новой
            connection.rollback()
            if waiting == count:
                return
            time.sleep(0.02)
    raise AssertionError(f"Не дождались {count} запросов, ждущих блокировку")


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
