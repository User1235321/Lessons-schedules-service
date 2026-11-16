from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, text

from app.domain.shared.ids import JobId


class PostgresJobExecutionLock:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @contextmanager
    def acquire(self, job_id: JobId) -> Iterator[bool]:
        key = job_id.int & ((1 << 63) - 1)
        with self._engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            acquired = bool(
                connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key})
            )
            try:
                yield acquired
            finally:
                if acquired:
                    connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
