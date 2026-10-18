from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase

# Предсказуемые имена ограничений: Alembic может сравнивать и удалять их в миграциях.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    # Всё время в базе хранится с часовым поясом: Clock отдаёт время в UTC (HLD 15.3).
    type_annotation_map: ClassVar[dict[Any, Any]] = {datetime: DateTime(timezone=True)}
