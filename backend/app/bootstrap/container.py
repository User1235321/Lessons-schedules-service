from dataclasses import dataclass
from datetime import timedelta

from confluent_kafka import Producer
from redis import Redis
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.application.academic.groups import (
    CreateGroup,
    CreateSubgroup,
    DeleteGroup,
    DeleteSubgroup,
    GetGroup,
    GetSubgroup,
    ListGroups,
    ListSubgroups,
    UpdateGroup,
    UpdateSubgroup,
)
from app.application.academic.rooms import (
    CreateRoom,
    DeleteRoom,
    GetRoom,
    ListRooms,
    UpdateRoom,
)
from app.application.academic.streams import (
    CreateStream,
    DeleteStream,
    GetStream,
    ListStreams,
    UpdateStream,
)
from app.application.academic.subjects import (
    CreateSubject,
    DeleteSubject,
    GetSubject,
    ListSubjects,
    UpdateSubject,
)
from app.application.academic.teachers import (
    CreateTeacher,
    DeleteTeacher,
    GetTeacher,
    ListTeachers,
    UpdateTeacher,
)
from app.application.academic.workloads import (
    CreateWorkload,
    DeleteWorkload,
    GetWorkload,
    ListWorkloads,
    UpdateWorkload,
)
from app.application.auth.password_reset import ConfirmPasswordReset, RequestPasswordReset
from app.application.auth.ports import MailSender, PasswordHasher, TokenService
from app.application.auth.use_cases import (
    Authenticate,
    GetCurrentUser,
    Login,
    Logout,
    Refresh,
    Register,
    SessionIssuer,
)
from app.application.constraints.use_cases import (
    CreateConstraint,
    DeleteConstraint,
    ListConstraints,
    ListCriteria,
    ReplaceCriteria,
    UpdateConstraint,
)
from app.application.projects.use_cases import (
    CreateProject,
    DeleteProject,
    GetProject,
    ListProjects,
    UpdateProject,
)
from app.application.scheduling.delivery import DeliverPendingJob
from app.application.scheduling.ports import JobProblemSource, JobStateStore, ScheduleProblemSolver
from app.application.scheduling.processing import ProcessJob
from app.application.scheduling.schedules import GetSchedule, UpdateScheduleEntry, ValidateSchedule
from app.application.scheduling.use_cases import (
    CancelGenerationJob,
    CreateGenerationJob,
    GetGenerationJob,
    GetGenerationSchedules,
)
from app.application.shared.ports import Clock, IdGenerator
from app.application.shared.uow import UnitOfWork
from app.bootstrap.settings import Settings
from app.infrastructure.job_state import RedisJobStateStore
from app.infrastructure.mail import SMTPMailSender
from app.infrastructure.messaging.kafka import KafkaJobPublisher
from app.infrastructure.persistence.database import create_database_engine, create_session_factory
from app.infrastructure.persistence.job_lock import PostgresJobExecutionLock
from app.infrastructure.persistence.job_problem import SqlJobProblemSource
from app.infrastructure.persistence.uow import SqlUnitOfWork
from app.infrastructure.security import Argon2PasswordHasher, JwtTokenService
from app.infrastructure.system import SystemClock, UuidGenerator
from app.scheduling.preview import PreviewScheduleSolver


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
    mail_sender: MailSender

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

    def request_password_reset(self) -> RequestPasswordReset:
        base_url = self.settings.password_reset_base_url
        return RequestPasswordReset(
            uow=self.uow(),
            mail=self.mail_sender,
            clock=self.clock,
            ttl_minutes=self.settings.password_reset_token_ttl_minutes,
            base_url=str(base_url) if base_url is not None else None,
        )

    def confirm_password_reset(self) -> ConfirmPasswordReset:
        return ConfirmPasswordReset(uow=self.uow(), passwords=self.passwords, clock=self.clock)

    def logout(self) -> Logout:
        return Logout(uow=self.uow(), tokens=self.tokens, clock=self.clock)

    def authenticate(self) -> Authenticate:
        return Authenticate(tokens=self.tokens, clock=self.clock)

    def get_current_user(self) -> GetCurrentUser:
        return GetCurrentUser(uow=self.uow())

    def create_project(self) -> CreateProject:
        return CreateProject(uow=self.uow(), clock=self.clock, ids=self.ids)

    def list_projects(self) -> ListProjects:
        return ListProjects(uow=self.uow())

    def get_project(self) -> GetProject:
        return GetProject(uow=self.uow())

    def update_project(self) -> UpdateProject:
        return UpdateProject(uow=self.uow(), clock=self.clock)

    def delete_project(self) -> DeleteProject:
        return DeleteProject(uow=self.uow())

    def create_subject(self) -> CreateSubject:
        return CreateSubject(uow=self.uow(), clock=self.clock, ids=self.ids)

    def list_subjects(self) -> ListSubjects:
        return ListSubjects(uow=self.uow())

    def get_subject(self) -> GetSubject:
        return GetSubject(uow=self.uow())

    def update_subject(self) -> UpdateSubject:
        return UpdateSubject(uow=self.uow(), clock=self.clock)

    def delete_subject(self) -> DeleteSubject:
        return DeleteSubject(uow=self.uow(), clock=self.clock)

    def create_teacher(self) -> CreateTeacher:
        return CreateTeacher(uow=self.uow(), clock=self.clock, ids=self.ids)

    def list_teachers(self) -> ListTeachers:
        return ListTeachers(uow=self.uow())

    def get_teacher(self) -> GetTeacher:
        return GetTeacher(uow=self.uow())

    def update_teacher(self) -> UpdateTeacher:
        return UpdateTeacher(uow=self.uow(), clock=self.clock)

    def delete_teacher(self) -> DeleteTeacher:
        return DeleteTeacher(uow=self.uow(), clock=self.clock)

    def create_group(self) -> CreateGroup:
        return CreateGroup(uow=self.uow(), clock=self.clock, ids=self.ids)

    def list_groups(self) -> ListGroups:
        return ListGroups(uow=self.uow())

    def get_group(self) -> GetGroup:
        return GetGroup(uow=self.uow())

    def update_group(self) -> UpdateGroup:
        return UpdateGroup(uow=self.uow(), clock=self.clock)

    def delete_group(self) -> DeleteGroup:
        return DeleteGroup(uow=self.uow(), clock=self.clock)

    def create_subgroup(self) -> CreateSubgroup:
        return CreateSubgroup(uow=self.uow(), clock=self.clock, ids=self.ids)

    def list_subgroups(self) -> ListSubgroups:
        return ListSubgroups(uow=self.uow())

    def get_subgroup(self) -> GetSubgroup:
        return GetSubgroup(uow=self.uow())

    def update_subgroup(self) -> UpdateSubgroup:
        return UpdateSubgroup(uow=self.uow(), clock=self.clock)

    def delete_subgroup(self) -> DeleteSubgroup:
        return DeleteSubgroup(uow=self.uow(), clock=self.clock)

    def create_room(self) -> CreateRoom:
        return CreateRoom(uow=self.uow(), clock=self.clock, ids=self.ids)

    def list_rooms(self) -> ListRooms:
        return ListRooms(uow=self.uow())

    def get_room(self) -> GetRoom:
        return GetRoom(uow=self.uow())

    def update_room(self) -> UpdateRoom:
        return UpdateRoom(uow=self.uow(), clock=self.clock)

    def delete_room(self) -> DeleteRoom:
        return DeleteRoom(uow=self.uow(), clock=self.clock)

    def create_stream(self) -> CreateStream:
        return CreateStream(uow=self.uow(), clock=self.clock, ids=self.ids)

    def list_streams(self) -> ListStreams:
        return ListStreams(uow=self.uow())

    def get_stream(self) -> GetStream:
        return GetStream(uow=self.uow())

    def update_stream(self) -> UpdateStream:
        return UpdateStream(uow=self.uow(), clock=self.clock)

    def delete_stream(self) -> DeleteStream:
        return DeleteStream(uow=self.uow(), clock=self.clock)

    def create_workload(self) -> CreateWorkload:
        return CreateWorkload(uow=self.uow(), clock=self.clock, ids=self.ids)

    def list_workloads(self) -> ListWorkloads:
        return ListWorkloads(uow=self.uow())

    def get_workload(self) -> GetWorkload:
        return GetWorkload(uow=self.uow())

    def update_workload(self) -> UpdateWorkload:
        return UpdateWorkload(uow=self.uow(), clock=self.clock)

    def delete_workload(self) -> DeleteWorkload:
        return DeleteWorkload(uow=self.uow(), clock=self.clock)

    def create_constraint(self) -> CreateConstraint:
        return CreateConstraint(uow=self.uow(), clock=self.clock, ids=self.ids)

    def list_constraints(self) -> ListConstraints:
        return ListConstraints(uow=self.uow())

    def update_constraint(self) -> UpdateConstraint:
        return UpdateConstraint(uow=self.uow(), clock=self.clock)

    def delete_constraint(self) -> DeleteConstraint:
        return DeleteConstraint(uow=self.uow(), clock=self.clock)

    def list_criteria(self) -> ListCriteria:
        return ListCriteria(uow=self.uow())

    def replace_criteria(self) -> ReplaceCriteria:
        return ReplaceCriteria(uow=self.uow(), clock=self.clock)

    def job_state(self) -> JobStateStore:
        return RedisJobStateStore(self.redis)

    def close(self) -> None:
        self.redis.close()
        self.engine.dispose()

    def create_generation_job(self) -> CreateGenerationJob:
        return CreateGenerationJob(uow=self.uow(), clock=self.clock, ids=self.ids)

    def get_generation_job(self) -> GetGenerationJob:
        return GetGenerationJob(uow=self.uow(), state=self.job_state())

    def get_generation_schedules(self) -> GetGenerationSchedules:
        return GetGenerationSchedules(uow=self.uow())

    def get_schedule(self) -> GetSchedule:
        return GetSchedule(uow=self.uow())

    def update_schedule_entry(self) -> UpdateScheduleEntry:
        return UpdateScheduleEntry(uow=self.uow())

    def validate_schedule(self) -> ValidateSchedule:
        return ValidateSchedule(uow=self.uow())

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
            problems=problems if problems is not None else SqlJobProblemSource(self.session_factory),
            solver=solver if solver is not None else PreviewScheduleSolver(),
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
        mail_sender=SMTPMailSender(
            host=settings.mail_host,
            port=settings.mail_port,
            username=settings.mail_username,
            password=settings.mail_password.get_secret_value(),
            sender=settings.mail_from,
        ),
        redis=Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
            decode_responses=True,
        ),
    )
