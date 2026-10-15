from alembic import command
from sqlalchemy import Connection, text

from tests.database import alembic_config


def test_database_is_reachable(db_connection: Connection) -> None:
    assert db_connection.execute(text("SELECT 1")).scalar_one() == 1


def test_migrations_match_models(db_connection: Connection) -> None:
    # Падает, если модель изменили, а миграцию не написали (или наоборот).
    command.check(alembic_config(db_connection))


def test_migrations_roll_back_and_reapply(db_connection: Connection) -> None:
    # Каждая миграция обязана откатываться: до base и обратно до head.
    config = alembic_config(db_connection)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
