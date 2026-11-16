from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.api_calls import created, new_project, sign_in
from tests.fakes import FakeClock

COLLECTIONS = ("subjects", "teachers", "groups", "subgroups")


@pytest.mark.parametrize("collection", COLLECTIONS)
def test_academic_data_requires_sign_in(api: TestClient, collection: str) -> None:  # NF_Security_1
    response = api.get(f"/projects/{uuid4()}/{collection}")

    assert response.status_code == 401


@pytest.mark.parametrize("collection", COLLECTIONS)
def test_foreign_project_data_looks_missing(
    api: TestClient, collection: str
) -> None:  # NF_Security_2
    owner, stranger = sign_in(api, "owner@mail.ru"), sign_in(api, "stranger@mail.ru")
    foreign, missing = new_project(api, owner), str(uuid4())

    for project in (foreign, missing):
        response = api.get(f"/projects/{project}/{collection}", headers=stranger)
        assert response.status_code == 404
        assert response.json()["code"] == "NOT_FOUND"


def test_subject_lifecycle(api: TestClient) -> None:
    user = sign_in(api)
    path = f"/projects/{new_project(api, user)}/subjects"

    physics = created(api, path, user, {"name": "  Физика "})
    math = created(api, path, user, {"name": "алгебра"})
    renamed = api.patch(f"{path}/{physics['id']}", json={"name": "Физика (лабы)"}, headers=user)

    assert physics["name"] == "Физика"
    assert renamed.json() == {"id": physics["id"], "name": "Физика (лабы)"}
    assert api.get(path, headers=user).json() == [math, renamed.json()]
    assert api.delete(f"{path}/{math['id']}", headers=user).status_code == 204
    assert api.get(f"{path}/{math['id']}", headers=user).status_code == 404


def test_subject_name_is_required_and_unique(api: TestClient) -> None:  # F_Valid_2
    user = sign_in(api)
    path = f"/projects/{new_project(api, user)}/subjects"
    created(api, path, user, {"name": "Математика"})

    blank = api.post(path, json={"name": " "}, headers=user)
    taken = api.post(path, json={"name": "МАТЕМАТИКА"}, headers=user)

    assert (blank.status_code, blank.json()["details"]) == (422, {"field": "name"})
    assert taken.status_code == 409
    assert taken.json()["code"] == "SUBJECT_NAME_TAKEN"
    assert taken.json()["details"] == {"field": "name"}


def test_subject_in_use_is_not_deleted(api: TestClient) -> None:
    user = sign_in(api)
    project = new_project(api, user)
    math = created(api, f"/projects/{project}/subjects", user, {"name": "Математика"})
    petrova = created(
        api,
        f"/projects/{project}/teachers",
        user,
        {
            "full_name": "Петрова А. В.",
            "capabilities": [{"subject_id": math["id"], "lesson_type": "LECTURE"}],
            "availability": [{"week": "ODD", "day": "MONDAY", "start": "09:00", "end": "13:00"}],
        },
    )

    response = api.delete(f"/projects/{project}/subjects/{math['id']}", headers=user)

    assert response.status_code == 409
    assert response.json() == {
        "code": "SUBJECT_IN_USE",
        "message": "Дисциплина используется у преподавателей",
        "details": {"teachers": [{"id": petrova["id"], "full_name": "Петрова А. В."}]},
    }


def test_editing_data_moves_project_up(api: TestClient, clock: FakeClock) -> None:
    user = sign_in(api)
    edited = new_project(api, user, "Старый")
    clock.advance(timedelta(minutes=1))
    new_project(api, user, "Новый")
    clock.advance(timedelta(minutes=1))

    subject = created(api, f"/projects/{edited}/subjects", user, {"name": "Физика"})

    projects = api.get("/projects", headers=user).json()
    assert [project["name"] for project in projects] == ["Старый", "Новый"]
    assert projects[0]["updated_at"] > projects[0]["created_at"]

    clock.advance(timedelta(minutes=1))
    before = projects[0]["updated_at"]
    api.patch(f"/projects/{edited}/subjects/{subject['id']}", json={}, headers=user)
    assert api.get(f"/projects/{edited}", headers=user).json()["updated_at"] == before
