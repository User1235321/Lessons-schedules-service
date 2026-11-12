from dataclasses import dataclass
from datetime import timedelta

from confluent_kafka import Producer
from redis import Redis
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
from app.application.scheduling.delivery import DeliverPendingJob
from app.application.scheduling.ports import JobProblemSource, JobStateStore, ScheduleProblemSolver
from app.application.scheduling.processing import ProcessJob
from app.application.scheduling.use_cases import (
    CancelGenerationJob,
    CreateGenerationJob,
    GetGenerationJob,
)
from app.application.shared.ports import Clock, IdGenerator
from app.application.shared.uow import UnitOfWork
from app.bootstrap.settings import Settings
from app.infrastructure.job_state import RedisJobStateStore
from app.infrastructure.messaging.kafka import KafkaJobPublisher
from app.infrastructure.persistence.database import create_database_engine, create_session_factory
from app.infrastructure.persistence.job_lock import PostgresJobExecutionLock
from app.infrastructure.persistence.uow import SqlUnitOfWork
from app.infrastructure.security import Argon2PasswordHasher, JwtTokenService
from app.infrastructure.system import SystemClock, UuidGenerator
from app.infrastructure.unavailable_scheduling import (
    UnavailableJobProblemSource,
    UnavailableScheduleSolver,
)


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
    redis: Redis

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

    def job_state(self) -> JobStateStore:
        return RedisJobStateStore(self.redis)

    def close(self) -> None:
        self.redis.close()
        self.engine.dispose()

    def create_generation_job(self) -> CreateGenerationJob:
        return CreateGenerationJob(uow=self.uow(), clock=self.clock, ids=self.ids)

    def get_generation_job(self) -> GetGenerationJob:
        return GetGenerationJob(uow=self.uow(), state=self.job_state())

    def cancel_generation_job(self) -> CancelGenerationJob:
        return CancelGenerationJob(uow=self.uow(), state=self.job_state())

    def deliver_pending_job(self) -> DeliverPendingJob:
        producer = Producer(
            {
                "bootstrap.servers": self.settings.kafka_bootstrap_servers,
                "enable.idempotence": True,
                "acks": "all",
                "message.timeout.ms": 10000,
            }
        )
        return DeliverPendingJob(
            uow=self.uow(), publisher=KafkaJobPublisher(producer), clock=self.clock
        )

    def process_job(
        self,
        *,
        problems: JobProblemSource | None = None,
        solver: ScheduleProblemSolver | None = None,
    ) -> ProcessJob:
        return ProcessJob(
            uow=self.uow(),
            lock=PostgresJobExecutionLock(self.engine),
            state=self.job_state(),
            problems=problems if problems is not None else UnavailableJobProblemSource(),
            solver=solver if solver is not None else UnavailableScheduleSolver(),
            clock=self.clock,
            ids=self.ids,
        )

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
        redis=Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
            decode_responses=True,
        ),
    )
