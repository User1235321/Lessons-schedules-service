from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import Connection

from app.domain.auth.user import Email, User
from app.domain.projects.project import Project
from app.domain.projects.settings import DurationMode, ProjectSettings, StudyCycle, TimeMode
from app.domain.shared.errors import NotFound
from app.domain.shared.ids import ProjectId, UserId
from app.domain.shared.week import Weekday
from app.infrastructure.persistence.uow import SqlUnitOfWork
from tests.database import recorded_statements

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


def stored_user(uow: SqlUnitOfWork, email: str = "ivan@mail.ru") -> User:
    user = User(id=UserId(uuid4()), email=Email(email), password_hash="hash", created_at=NOW)
    with uow:
        uow.users.add(user)
        uow.commit()
    return user


def a_project(owner: User, name: str = "Осенний семестр", now: datetime = NOW) -> Project:
    return Project.create(project_id=ProjectId(uuid4()), owner_id=owner.id, name=name, now=now)


def store(uow: SqlUnitOfWork, *projects: Project) -> None:
    with uow:
        for project in projects:
            uow.projects.add(project)
        uow.commit()


@pytest.mark.parametrize(
    "settings",
    [
        ProjectSettings.default(),
        ProjectSettings(
            cycle=StudyCycle((Weekday.MONDAY, Weekday.THURSDAY), ()),
            time_mode=TimeMode.step(15),
            duration_mode=DurationMode.individual(),
        ),
    ],
    ids=["default", "step and individual"],
)
def test_project_is_stored_without_losses(uow: SqlUnitOfWork, settings: ProjectSettings) -> None:
    owner = stored_user(uow)
    project = Project.create(
        project_id=ProjectId(uuid4()), owner_id=owner.id, name="Весна", now=NOW, settings=settings
    )
    store(uow, project)

    with uow:
        assert uow.projects.get_owned(project.id, owner.id) == project


def test_project_of_another_user_is_not_found(uow: SqlUnitOfWork) -> None:
    owner = stored_user(uow, "owner@mail.ru")
    stranger = stored_user(uow, "stranger@mail.ru")
    project = a_project(owner)
    store(uow, project)

    with uow:
        assert uow.projects.get_owned(project.id, stranger.id) is None  # NF_Security_2


def test_list_contains_only_own_projects_recently_changed_first(uow: SqlUnitOfWork) -> None:
    owner = stored_user(uow, "owner@mail.ru")
    stranger = stored_user(uow, "stranger@mail.ru")
    old = a_project(owner, "Старый", now=NOW)
    new = a_project(owner, "Новый", now=NOW + timedelta(days=1))
    store(uow, old, new, a_project(stranger, "Чужой"))

    with uow:
        assert [project.name for project in uow.projects.list_owned(owner.id)] == [
            "Новый",
            "Старый",
        ]


def test_saved_changes_are_persisted(uow: SqlUnitOfWork) -> None:
    owner = stored_user(uow)
    project = a_project(owner)
    store(uow, project)
    later = NOW + timedelta(hours=1)

    with uow:
        stored = uow.projects.get_owned(project.id, owner.id)
        assert stored is not None
        stored.rename("Весенний семестр", later)
        stored.change_settings(
            ProjectSettings(
                cycle=StudyCycle((Weekday.SATURDAY,), (Weekday.SATURDAY,)),
                time_mode=TimeMode.step(30),
                duration_mode=DurationMode.uniform(90),
            ),
            later,
        )
        uow.projects.save(stored)
        uow.commit()

    with uow:
        assert uow.projects.get_owned(project.id, owner.id) == stored


def test_saving_is_a_single_update(uow: SqlUnitOfWork, db_connection: Connection) -> None:
    owner = stored_user(uow)
    project = a_project(owner)
    store(uow, project)

    with uow:
        stored = uow.projects.get_owned(project.id, owner.id)
        assert stored is not None
        stored.rename("Весенний семестр", NOW + timedelta(hours=1))
        with recorded_statements(db_connection) as statements:
            uow.projects.save(stored)

    assert statements == ["UPDATE"]


def test_saving_missing_project_fails(uow: SqlUnitOfWork) -> None:
    owner = stored_user(uow)

    with uow, pytest.raises(NotFound):
        uow.projects.save(a_project(owner))


def test_deleted_project_is_gone_and_others_stay(uow: SqlUnitOfWork) -> None:
    owner = stored_user(uow)
    doomed, kept = a_project(owner, "Удаляемый"), a_project(owner, "Остаётся")
    store(uow, doomed, kept)

    with uow:
        uow.projects.delete(doomed.id)
        uow.commit()

    with uow:
        assert uow.projects.list_owned(owner.id) == [kept]
