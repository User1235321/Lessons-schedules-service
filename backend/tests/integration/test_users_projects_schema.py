"""Ограничения схемы, которые сущность проверить не может или которые страхуют её в базе."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.persistence.models import ProjectRow, UserRow, UserSessionRow

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


def a_user(email: str = "ivan@mail.ru") -> UserRow:
    return UserRow(id=uuid4(), email=email, password_hash="hash", created_at=NOW)


def a_session(user: UserRow) -> UserSessionRow:
    return UserSessionRow(
        id=uuid4(),
        user_id=user.id,
        refresh_token_hash=f"hash-{uuid4()}",
        created_at=NOW,
        expires_at=NOW + timedelta(days=30),
    )


def a_project(owner: UserRow, **overrides: object) -> ProjectRow:
    values: dict[str, object] = {
        "id": uuid4(),
        "owner_id": owner.id,
        "name": "Осенний семестр",
        "odd_week_days": ["MONDAY", "TUESDAY"],
        "even_week_days": ["MONDAY"],
        "time_mode": "HOUR_START",
        "time_step_minutes": None,
        "duration_mode": "UNIFORM",
        "duration_minutes": 100,
        "created_at": NOW,
        "updated_at": NOW,
    }
    return ProjectRow(**(values | overrides))


def test_user_project_and_session_are_stored(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        user = a_user()
        session.add(user)
        session.flush()
        session.add_all([a_session(user), a_project(user, time_mode="STEP", time_step_minutes=30)])
        session.commit()

    with session_factory() as session:
        project = session.scalars(select(ProjectRow)).one()
        assert project.odd_week_days == ["MONDAY", "TUESDAY"]
        assert project.time_step_minutes == 30
        assert project.created_at == NOW  # timestamptz возвращает время с поясом
        assert session.scalars(select(UserSessionRow)).one().revoked_at is None


def test_email_is_unique(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        session.add(a_user("ivan@mail.ru"))
        session.flush()
        session.add(a_user("ivan@mail.ru"))

        with pytest.raises(IntegrityError, match="uq_users_email"):
            session.flush()


def test_email_must_be_lowercase(session_factory: sessionmaker[Session]) -> None:
    # Иначе Ivan@mail.ru прошёл бы мимо UNIQUE рядом с ivan@mail.ru (F_Auth_3)
    with session_factory() as session:
        session.add(a_user("Ivan@mail.ru"))

        with pytest.raises(IntegrityError, match="ck_users_email_lowercase"):
            session.flush()


@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        ({"name": "   "}, "name_not_blank"),
        ({"odd_week_days": ["MONDAY", "FUNDAY"]}, "odd_week_days_known"),
        ({"even_week_days": ["SOMEDAY"]}, "even_week_days_known"),
        ({"time_mode": "ANY_TIME"}, "time_mode_known"),
        ({"time_mode": "STEP", "time_step_minutes": None}, "time_step_matches_mode"),
        ({"time_mode": "HOUR_START", "time_step_minutes": 30}, "time_step_matches_mode"),
        ({"time_mode": "STEP", "time_step_minutes": 0}, "time_step_positive"),
        ({"duration_mode": "FREE", "duration_minutes": None}, "duration_mode_known"),
        ({"duration_mode": "UNIFORM", "duration_minutes": None}, "duration_matches_mode"),
        ({"duration_mode": "INDIVIDUAL", "duration_minutes": 100}, "duration_matches_mode"),
        ({"duration_minutes": -100}, "duration_positive"),
    ],
    ids=[
        "blank name",
        "unknown odd day",
        "unknown even day",
        "unknown time mode",
        "step mode without step",
        "hour start with step",
        "zero step",
        "unknown duration mode",
        "uniform without duration",
        "individual with duration",
        "negative duration",
    ],
)
def test_project_settings_are_checked(
    session_factory: sessionmaker[Session], overrides: dict[str, object], constraint: str
) -> None:
    with session_factory() as session:
        user = a_user()
        session.add(user)
        session.flush()
        session.add(a_project(user, **overrides))

        with pytest.raises(IntegrityError, match=f"ck_projects_{constraint}"):
            session.flush()


def test_deleting_user_deletes_sessions_and_projects(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        user = a_user()
        session.add(user)
        session.flush()
        session.add_all([a_session(user), a_project(user), a_project(user)])
        session.commit()

        session.delete(user)
        session.commit()

        assert session.scalars(select(ProjectRow)).all() == []
        assert session.scalars(select(UserSessionRow)).all() == []
