import os
from collections.abc import Iterator

import pytest
from alembic import command
from sqlalchemy import Connection, Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.persistence.uow import SqlUnitOfWork
from tests.database import POSTGRES_IMAGE, alembic_config


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Всё, что лежит в tests/integration, получает маркер integration."""
    for item in items:
        if "integration" in item.path.parts:
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """Чистый PostgreSQL в Docker на всю сессию тестов."""
    from testcontainers.community.postgres import PostgresContainer

    try:
        # Клиент Docker подключается уже в конструкторе, поэтому он тоже внутри try
        container = PostgresContainer(POSTGRES_IMAGE, driver="psycopg")
        container.start()
    except Exception as error:
        # В CI тест должен упасть, а локально без Docker — пропуститься с понятной причиной.
        if os.environ.get("CI"):
            raise
        pytest.skip(f"Не удалось запустить PostgreSQL в Docker: {error}")
    try:
        yield container.get_connection_url()
    finally:
        container.stop()


@pytest.fixture(scope="session")
def migrated_engine(database_url: str) -> Iterator[Engine]:
    engine = create_engine(database_url)
    with engine.begin() as connection:
        command.upgrade(alembic_config(connection), "head")
    yield engine
    engine.dispose()


@pytest.fixture
def db_connection(migrated_engine: Engine) -> Iterator[Connection]:
    """Соединение с внешней транзакцией: всё, что сделал тест, откатывается."""
    with migrated_engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()


@pytest.fixture
def session_factory(db_connection: Connection) -> sessionmaker[Session]:
    # commit() в коде приложения отпускает точку сохранения, а не внешнюю транзакцию
    return sessionmaker(
        bind=db_connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )


@pytest.fixture
def uow(session_factory: sessionmaker[Session]) -> SqlUnitOfWork:
    return SqlUnitOfWork(session_factory)
