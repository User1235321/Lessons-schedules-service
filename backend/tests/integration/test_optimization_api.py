from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.persistence.models import (
    ExtraConstraintRow,
    OptimizationCriterionRow,
)
from tests.api_calls import created, new_project, sign_in

TYPES = (
    "STUDENT_GAPS",
    "TEACHER_GAPS",
    "TEACHER_PREFERENCES",
    "BALANCED_STUDENT_LOAD",
    "EARLY_LATE_CLASSES",
)


def endpoint(project: str) -> str:
    return f"/projects/{project}/optimization-criteria"


def criteria(items: tuple[str, ...] = TYPES) -> list[dict]:
    return [
        {"criterion_type": kind, "priority": index, "is_active": True}
        for index, kind in enumerate(items, 1)
    ]


def test_all_five_criteria_can_be_saved_reordered_and_deactivated(api: TestClient) -> None:
    user = sign_in(api)
    project = new_project(api, user)
    path = endpoint(project)
    initial = criteria()
    response = api.put(path, headers=user, json={"criteria": initial})

    assert response.status_code == 200
    assert response.json() == initial
    assert api.get(path, headers=user).json() == initial

    updated = [
        {"criterion_type": kind, "priority": 1 if index in (1, 2) else index, "is_active": index == 1}
        for index, kind in enumerate(TYPES, 1)
    ]
    result = api.put(path, headers=user, json={"criteria": updated})

    assert result.status_code == 200
    assert sorted(result.json(), key=lambda item: item["criterion_type"]) == sorted(
        updated, key=lambda item: item["criterion_type"]
    )
    assert api.put(path, headers=user, json={"criteria": []}).json() == []
    assert api.get(path, headers=user).json() == []


@pytest.mark.parametrize(
    "invalid",
    [
        [{"criterion_type": "STUDENT_GAPS", "priority": 1, "is_active": True},
         {"criterion_type": "TEACHER_GAPS", "priority": 1, "is_active": True}],
        [{"criterion_type": "STUDENT_GAPS", "priority": 1, "is_active": True},
         {"criterion_type": "STUDENT_GAPS", "priority": 2, "is_active": False}],
        [{"criterion_type": "UNKNOWN", "priority": 1, "is_active": True}],
        [{"criterion_type": "TEACHER_GAPS", "priority": 0, "is_active": True}],
    ],
)
def test_invalid_criteria_do_not_replace_saved_values(api: TestClient, invalid: list) -> None:
    user = sign_in(api)
    project = new_project(api, user)
    path = endpoint(project)
    original = criteria(("STUDENT_GAPS",))
    assert api.put(path, headers=user, json={"criteria": original}).status_code == 200

    response = api.put(path, headers=user, json={"criteria": invalid})

    assert response.status_code == 422
    assert api.get(path, headers=user).json() == original


def test_criteria_require_ownership(api: TestClient) -> None:
    owner = sign_in(api, f"{uuid4()}@example.org")
    stranger = sign_in(api, f"{uuid4()}@example.org")
    project = new_project(api, owner)
    path = endpoint(project)

    assert api.get(path).status_code == 401
    assert api.get(path, headers=stranger).status_code == 404
    assert api.put(path, headers=stranger, json={"criteria": criteria()}).status_code == 404


def test_database_rejects_duplicate_active_priority(
    api: TestClient, session_factory: sessionmaker[Session]
) -> None:
    user = sign_in(api)
    project = new_project(api, user)
    assert api.put(
        endpoint(project), json={"criteria": criteria(("STUDENT_GAPS",))}, headers=user
    ).status_code == 200

    with session_factory() as session, session.begin_nested(), pytest.raises(IntegrityError):
        session.add(
            OptimizationCriterionRow(
                project_id=UUID(project),
                criterion_type="TEACHER_GAPS",
                priority=1,
                is_active=True,
            )
        )
        session.flush()


def test_project_deletion_removes_persisted_settings(
    api: TestClient, session_factory: sessionmaker[Session]
) -> None:
    user = sign_in(api)
    project = new_project(api, user)
    created(
        api,
        f"/projects/{project}/constraints",
        user,
        {
            "constraint_type": "MIN_START_TIME",
            "scope": {"type": "PROJECT"},
            "parameters": {"time": "10:00"},
        },
    )
    assert api.put(
        endpoint(project), json={"criteria": criteria()}, headers=user
    ).status_code == 200

    assert api.delete(f"/projects/{project}", headers=user).status_code == 204
    with session_factory() as session:
        assert session.scalars(
            select(ExtraConstraintRow).where(ExtraConstraintRow.project_id == UUID(project))
        ).all() == []
        assert session.scalars(
            select(OptimizationCriterionRow).where(
                OptimizationCriterionRow.project_id == UUID(project)
            )
        ).all() == []
