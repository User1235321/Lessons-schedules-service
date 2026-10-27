from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.application.auth.access import owned_project
from app.domain.auth.user import Email, User
from app.domain.projects.project import Project
from app.domain.shared.errors import NotFound
from app.domain.shared.ids import ProjectId, UserId
from app.infrastructure.persistence.uow import SqlUnitOfWork

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)


def stored_user(uow: SqlUnitOfWork, email: str) -> User:
    user = User(id=UserId(uuid4()), email=Email(email), password_hash="hash", created_at=NOW)
    with uow:
        uow.users.add(user)
        uow.commit()
    return user


def stored_project(uow: SqlUnitOfWork, owner: User) -> Project:
    project = Project.create(
        project_id=ProjectId(uuid4()), owner_id=owner.id, name="Осень", now=NOW
    )
    with uow:
        uow.projects.add(project)
        uow.commit()
    return project


def test_owner_gets_project(uow: SqlUnitOfWork) -> None:  # F_Auth_7
    owner = stored_user(uow, "owner@mail.ru")
    project = stored_project(uow, owner)

    with uow:
        assert owned_project(uow, project.id, owner.id) == project


def test_foreign_project_looks_like_missing_one(uow: SqlUnitOfWork) -> None:  # NF_Security_2
    owner = stored_user(uow, "owner@mail.ru")
    stranger = stored_user(uow, "stranger@mail.ru")
    project = stored_project(uow, owner)
    missing_id = ProjectId(uuid4())

    with uow, pytest.raises(NotFound) as foreign:
        owned_project(uow, project.id, stranger.id)
    with uow, pytest.raises(NotFound) as missing:
        owned_project(uow, missing_id, stranger.id)

    assert foreign.value.message == missing.value.message
    assert foreign.value.details == {"project_id": str(project.id)}
    assert missing.value.details == {"project_id": str(missing_id)}
