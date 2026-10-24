from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.application.auth.ports import PasswordHasher, TokenService
from app.application.auth.use_cases import (
    Authenticate,
    GetCurrentUser,
    Login,
    Logout,
    Refresh,
    Register,
    SessionIssuer,
)
from app.application.shared.ports import Clock, IdGenerator
from app.application.shared.uow import UnitOfWork
from app.bootstrap.settings import Settings
from app.infrastructure.persistence.database import create_database_engine, create_session_factory
from app.infrastructure.persistence.uow import SqlUnitOfWork
from app.infrastructure.security import Argon2PasswordHasher, JwtTokenService
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
    passwords: PasswordHasher
    tokens: TokenService

    def uow(self) -> UnitOfWork:
        # Новая транзакция на каждый вызов: сценарии не делят сессию между запросами
        return SqlUnitOfWork(self.session_factory)

    def register(self) -> Register:
        return Register(
            uow=self.uow(),
            passwords=self.passwords,
            sessions=self._session_issuer(),
            clock=self.clock,
            ids=self.ids,
        )

    def login(self) -> Login:
        return Login(
            uow=self.uow(),
            passwords=self.passwords,
            sessions=self._session_issuer(),
            clock=self.clock,
        )

    def refresh(self) -> Refresh:
        return Refresh(uow=self.uow(), tokens=self.tokens, clock=self.clock)

    def logout(self) -> Logout:
        return Logout(uow=self.uow(), tokens=self.tokens, clock=self.clock)

    def authenticate(self) -> Authenticate:
        return Authenticate(tokens=self.tokens, clock=self.clock)

    def get_current_user(self) -> GetCurrentUser:
        return GetCurrentUser(uow=self.uow())

    def _session_issuer(self) -> SessionIssuer:
        return SessionIssuer(
            tokens=self.tokens,
            ids=self.ids,
            refresh_ttl=timedelta(days=self.settings.refresh_token_ttl_days),
        )


def build_container(settings: Settings) -> Container:
    engine = create_database_engine(settings.database_url, echo=settings.database_echo)
    return Container(
        settings=settings,
        engine=engine,
        session_factory=create_session_factory(engine),
        clock=SystemClock(),
        ids=UuidGenerator(),
        passwords=Argon2PasswordHasher(),
        tokens=JwtTokenService(
            settings.jwt_secret, access_ttl=timedelta(minutes=settings.access_token_ttl_minutes)
        ),
    )
