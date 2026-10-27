from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.application.auth.ports import PasswordHasher, TokenService
from app.application.shared.ports import Clock, IdGenerator
from app.application.shared.uow import UnitOfWork
from app.domain.auth.errors import InvalidCredentials
from app.domain.auth.session import UserSession
from app.domain.auth.user import Email, User, check_new_password
from app.domain.shared.ids import SessionId, UserId


@dataclass(frozen=True)
class Credentials:
    email: str
    password: str = field(repr=False)  # чтобы пароль не попал в лог или traceback


@dataclass(frozen=True, repr=False)  # токены, как и пароль, не должны попадать в логи
class AuthTokens:
    access_token: str
    refresh_token: str


@dataclass(frozen=True)
class SessionIssuer:
    """Открывает refresh-сессию и выдаёт пару токенов. Общий шаг регистрации и входа."""

    tokens: TokenService
    ids: IdGenerator
    refresh_ttl: timedelta

    def issue(self, uow: UnitOfWork, user_id: UserId, now: datetime) -> AuthTokens:
        refresh_token = self.tokens.new_refresh_token()
        session = UserSession.open(
            session_id=SessionId(self.ids.new_id()),
            user_id=user_id,
            refresh_token_hash=self.tokens.hash_refresh_token(refresh_token),
            now=now,
            ttl=self.refresh_ttl,
        )
        uow.user_sessions.add(session)
        return AuthTokens(
            access_token=self.tokens.issue_access_token(user_id, now),
            refresh_token=refresh_token,
        )


@dataclass(frozen=True)
class Register:
    """Регистрация по адресу и паролю (F_Auth_1–3). Сразу выполняет и вход."""

    uow: UnitOfWork
    passwords: PasswordHasher
    sessions: SessionIssuer
    clock: Clock
    ids: IdGenerator

    def execute(self, credentials: Credentials) -> AuthTokens:
        email = Email(credentials.email)
        check_new_password(credentials.password)
        now = self.clock.now()
        user = User(
            id=UserId(self.ids.new_id()),
            email=email,
            # Хеш считается до транзакции: соединение с базой не ждёт медленный Argon2
            password_hash=self.passwords.hash(credentials.password),
            created_at=now,
        )
        with self.uow:
            self.uow.users.add(user)
            tokens = self.sessions.issue(self.uow, user.id, now)
            self.uow.commit()
        return tokens


@dataclass(frozen=True)
class Login:
    """Вход по адресу и паролю (F_Auth_4, F_Auth_5)."""

    uow: UnitOfWork
    passwords: PasswordHasher
    sessions: SessionIssuer
    clock: Clock

    def execute(self, credentials: Credentials) -> AuthTokens:
        email = Email(credentials.email)
        with self.uow:
            user = self.uow.users.get_by_email(email)
            if user is None or not self.passwords.verify(credentials.password, user.password_hash):
                raise InvalidCredentials("Неверный адрес электронной почты или пароль")
            tokens = self.sessions.issue(self.uow, user.id, self.clock.now())
            self.uow.commit()
        return tokens
