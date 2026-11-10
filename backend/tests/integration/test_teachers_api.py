from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.api_calls import created, new_project, sign_in


def interval(week: str = "ODD", day: str = "MONDAY", start: str = "09:00", end: str = "18:00"):
    return {"week": week, "day": day, "start": start, "end": end}


@pytest.fixture
def user(api: TestClient) -> dict[str, str]:
    return sign_in(api)


@pytest.fixture
def project(api: TestClient, user: dict[str, str]) -> str:
    return new_project(api, user)


@pytest.fixture
def physics(api: TestClient, user: dict[str, str], project: str) -> str:
    return created(api, f"/projects/{project}/subjects", user, {"name": "Физика"})["id"]


def teacher_body(subject_id: str, **overrides: Any) -> dict[str, Any]:
    # Как в test-data/minimal-project.json
    body = {
        "full_name": "Иванов Иван Иванович",
        "capabilities": [
            {"subject_id": subject_id, "lesson_type": "LAB"},
            {"subject_id": subject_id, "lesson_type": "PRACTICE"},
        ],
        "availability": [
            interval("ODD", "MONDAY"),
            interval("ODD", "TUESDAY"),
            interval("EVEN", "MONDAY"),
            interval("EVEN", "TUESDAY"),
        ],
        "preferences": [interval("ANY", "MONDAY", "10:00", "15:00")],
    }
    return body | overrides


def test_teacher_is_created_as_sent(
    api: TestClient, user: dict[str, str], project: str, physics: str
) -> None:  # F_Data_4
    body = teacher_body(physics)

    teacher = created(api, f"/projects/{project}/teachers", user, body)

    # Наборы — множества: сервер упорядочивает их сам, пары — лекция, практика, лабораторная
    lab, practice = body["capabilities"]
    assert teacher == {"id": teacher["id"], **body, "capabilities": [practice, lab]}
    assert api.get(f"/projects/{project}/teachers/{teacher['id']}", headers=user).json() == teacher
    assert api.get(f"/projects/{project}/teachers", headers=user).json() == [teacher]


def test_preferences_are_optional_and_repeats_collapse(
    api: TestClient, user: dict[str, str], project: str, physics: str
) -> None:
    body = teacher_body(physics, availability=[interval(), interval()])
    del body["preferences"]

    teacher = created(api, f"/projects/{project}/teachers", user, body)

    assert teacher["preferences"] == []
    assert teacher["availability"] == [interval()]


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"full_name": " "}, "full_name"),
        ({"capabilities": []}, "capabilities"),
        ({"availability": []}, "availability"),
        (
            {"availability": [interval(), interval(start="12:00", end="12:00")]},
            "availability.1.end",
        ),
        ({"preferences": [interval(start="15:00", end="10:00")]}, "preferences.0.end"),
    ],
)
def test_invalid_teacher_names_the_field(
    api: TestClient,
    user: dict[str, str],
    project: str,
    physics: str,
    overrides: dict[str, Any],
    field: str,
) -> None:  # F_Data_4, F_Valid_1, F_Valid_2
    response = api.post(
        f"/projects/{project}/teachers", json=teacher_body(physics, **overrides), headers=user
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_VALUE"
    assert response.json()["details"] == {"field": field}


@pytest.mark.parametrize("bad_time", ["9:00", "09:00:00", "24:00", "09-00"])
def test_time_must_be_hours_and_minutes(
    api: TestClient, user: dict[str, str], project: str, physics: str, bad_time: str
) -> None:
    body = teacher_body(physics, availability=[interval(start=bad_time)])

    response = api.post(f"/projects/{project}/teachers", json=body, headers=user)

    assert response.status_code == 422
    assert response.json()["details"]["fields"][0]["field"] == "availability.0.start"


def test_capability_subject_must_be_in_project(
    api: TestClient, user: dict[str, str], project: str, physics: str
) -> None:
    foreign = created(
        api, f"/projects/{new_project(api, user, 'Другой')}/subjects", user, {"name": "Химия"}
    )
    capabilities = [
        {"subject_id": physics, "lesson_type": "LAB"},
        {"subject_id": foreign["id"], "lesson_type": "LAB"},
    ]

    response = api.post(
        f"/projects/{project}/teachers",
        json=teacher_body(physics, capabilities=capabilities),
        headers=user,
    )

    assert response.status_code == 422
    assert response.json()["details"] == {"field": "capabilities.1.subject_id"}


def test_patch_replaces_only_sent_sets(
    api: TestClient, user: dict[str, str], project: str, physics: str
) -> None:  # F_Data_5
    teacher = created(api, f"/projects/{project}/teachers", user, teacher_body(physics))
    path = f"/projects/{project}/teachers/{teacher['id']}"

    response = api.patch(
        path, json={"availability": [interval("ANY", "FRIDAY")], "preferences": []}, headers=user
    )

    assert response.status_code == 200
    assert response.json() == teacher | {
        "availability": [interval("ANY", "FRIDAY")],
        "preferences": [],
    }
    assert api.patch(path, json={}, headers=user).json() == response.json()


def test_deleted_teacher_is_gone(
    api: TestClient, user: dict[str, str], project: str, physics: str
) -> None:  # F_Data_5
    teacher = created(api, f"/projects/{project}/teachers", user, teacher_body(physics))
    path = f"/projects/{project}/teachers/{teacher['id']}"

    assert api.delete(path, headers=user).status_code == 204
    assert api.get(path, headers=user).status_code == 404
    assert api.delete(path, headers=user).status_code == 404
    assert api.delete(f"/projects/{project}/subjects/{physics}", headers=user).status_code == 204


def test_teacher_of_another_project_looks_missing(
    api: TestClient, user: dict[str, str], project: str, physics: str
) -> None:  # NF_Security_2
    teacher = created(api, f"/projects/{project}/teachers", user, teacher_body(physics))
    other = new_project(api, user, "Другой")

    for method in ("GET", "PATCH", "DELETE"):
        response = api.request(
            method, f"/projects/{other}/teachers/{teacher['id']}", json={}, headers=user
        )
        assert response.status_code == 404
    missing = api.get(f"/projects/{project}/teachers/{uuid4()}", headers=user)
    assert missing.status_code == 404
