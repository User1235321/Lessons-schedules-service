from dataclasses import dataclass

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.application.shared.ports import Clock, IdGenerator
from app.application.shared.uow import UnitOfWork
from app.bootstrap.settings import Settings
from app.infrastructure.persistence.database import create_database_engine, create_session_factory
from app.infrastructure.persistence.uow import SqlUnitOfWork
from app.infrastructure.system import SystemClock, UuidGenerator


@dataclass
class Container:
    """Корень композиции: единственное место, где порты связываются с реализациями.

    Сценарии добавляются сюда фабричными методами, например
    ``def register(self) -> Register``. Роутеры получают их через ``api.deps``.
    """

    settings: Settings
    engine: Engine
    session_factory: sessionmaker[Session]
    clock: Clock
    ids: IdGenerator

    def uow(self) -> UnitOfWork:
        # Новая транзакция на каждый вызов: сценарии не делят сессию между запросами
        return SqlUnitOfWork(self.session_factory)


def build_container(settings: Settings) -> Container:
    engine = create_database_engine(settings.database_url, echo=settings.database_echo)
    return Container(
        settings=settings,
        engine=engine,
        session_factory=create_session_factory(engine),
        clock=SystemClock(),
        ids=UuidGenerator(),
    )
