from dataclasses import dataclass
from datetime import timedelta

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
from app.application.projects.use_cases import (
    CreateProject,
    DeleteProject,
    GetProject,
    ListProjects,
    UpdateProject,
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
