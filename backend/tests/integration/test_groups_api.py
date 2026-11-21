from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.api_calls import created, new_project, sign_in


@pytest.fixture
def user(api: TestClient) -> dict[str, str]:
    return sign_in(api)


@pytest.fixture
def project(api: TestClient, user: dict[str, str]) -> str:
    return new_project(api, user)


def new_group(
    api: TestClient, user: dict[str, str], project: str, name: str = "301", students: int = 24
) -> dict:
    body = {"name": name, "student_count": students}
    return created(api, f"/projects/{project}/groups", user, body)


def new_subgroup(
    api: TestClient, user: dict[str, str], project: str, group_id: str, name: str, students: int
) -> dict:
    body = {"group_id": group_id, "name": name, "student_count": students}
    return created(api, f"/projects/{project}/subgroups", user, body)


def test_group_lifecycle(api: TestClient, user: dict[str, str], project: str) -> None:  # F_Data_10
    path = f"/projects/{project}/groups"
    group = new_group(api, user, project, "302", 26)
    other = new_group(api, user, project, "301", 24)

    renamed = api.patch(f"{path}/{group['id']}", json={"name": "302а"}, headers=user).json()

    assert group == {"id": group["id"], "name": "302", "student_count": 26, "availability": [], "subgroups": []}
    assert renamed == group | {"name": "302а"}
    assert api.get(path, headers=user).json() == [other, renamed]
    assert api.delete(f"{path}/{group['id']}", headers=user).status_code == 204
    assert api.get(f"{path}/{group['id']}", headers=user).status_code == 404


def test_group_name_is_unique_and_count_positive(
    api: TestClient, user: dict[str, str], project: str
) -> None:  # F_Valid_1
    new_group(api, user, project, "301а")
    path = f"/projects/{project}/groups"

    taken = api.post(path, json={"name": "301А", "student_count": 20}, headers=user)
    empty = api.post(path, json={"name": "302", "student_count": 0}, headers=user)

    assert (taken.status_code, taken.json()["code"]) == (409, "GROUP_NAME_TAKEN")
    assert (empty.status_code, empty.json()["details"]) == (422, {"field": "student_count"})


def test_subgroups_appear_inside_their_group(
    api: TestClient, user: dict[str, str], project: str
) -> None:  # F_Data_11
    group = new_group(api, user, project)
    second = new_subgroup(api, user, project, group["id"], "301-2", 12)
    first = new_subgroup(api, user, project, group["id"], "301-1", 12)

    reloaded = api.get(f"/projects/{project}/groups/{group['id']}", headers=user).json()

    assert first == {
        "id": first["id"],
        "group_id": group["id"],
        "name": "301-1",
        "student_count": 12,
        "availability": [],
    }
    assert reloaded["subgroups"] == [
        {"id": first["id"], "name": "301-1", "student_count": 12, "availability": []},
        {"id": second["id"], "name": "301-2", "student_count": 12, "availability": []},
    ]


def test_subgroups_cannot_outgrow_group(
    api: TestClient, user: dict[str, str], project: str
) -> None:
    group = new_group(api, user, project, students=24)
    first = new_subgroup(api, user, project, group["id"], "301-1", 12)
    path = f"/projects/{project}/subgroups"

    too_many = api.post(
        path, json={"group_id": group["id"], "name": "301-2", "student_count": 13}, headers=user
    )
    grown = api.patch(f"{path}/{first['id']}", json={"student_count": 25}, headers=user)
    shrunk = api.patch(
        f"/projects/{project}/groups/{group['id']}", json={"student_count": 11}, headers=user
    )

    assert too_many.status_code == grown.status_code == shrunk.status_code == 422  # F_Data_12
    assert too_many.json() == {
        "code": "SUBGROUPS_EXCEED_GROUP",
        "message": "В подгруппах 25 студентов, а в группе 24",
        "details": {
            "field": "student_count",
            "group_student_count": 24,
            "subgroups_student_count": 25,
        },
    }
    assert api.get(f"{path}/{first['id']}", headers=user).json()["student_count"] == 12


def test_subgroup_names_are_unique_in_group(
    api: TestClient, user: dict[str, str], project: str
) -> None:
    group, other = new_group(api, user, project, "301"), new_group(api, user, project, "302")
    new_subgroup(api, user, project, group["id"], "Первая", 10)
    new_subgroup(api, user, project, other["id"], "первая", 10)  # в другой группе можно

    response = api.post(
        f"/projects/{project}/subgroups",
        json={"group_id": group["id"], "name": "ПЕРВАЯ", "student_count": 5},
        headers=user,
    )

    assert (response.status_code, response.json()["code"]) == (409, "SUBGROUP_NAME_TAKEN")


def test_subgroup_needs_existing_group_of_project(
    api: TestClient, user: dict[str, str], project: str
) -> None:
    foreign_group = new_group(api, user, new_project(api, user, "Другой"))

    for group_id in (str(uuid4()), foreign_group["id"]):
        response = api.post(
            f"/projects/{project}/subgroups",
            json={"group_id": group_id, "name": "301-1", "student_count": 10},
            headers=user,
        )
        assert response.status_code == 422
        assert response.json()["details"] == {"field": "group_id"}


def test_subgroups_are_listed_and_filtered_by_group(
    api: TestClient, user: dict[str, str], project: str
) -> None:
    g301, g302 = new_group(api, user, project, "301"), new_group(api, user, project, "302")
    a = new_subgroup(api, user, project, g302["id"], "302-1", 10)
    b = new_subgroup(api, user, project, g301["id"], "301-1", 10)
    path = f"/projects/{project}/subgroups"

    assert api.get(path, headers=user).json() == [b, a]
    assert api.get(path, params={"group_id": g302["id"]}, headers=user).json() == [a]
    assert api.get(path, params={"group_id": str(uuid4())}, headers=user).status_code == 404


def test_subgroup_is_changed_and_deleted(
    api: TestClient, user: dict[str, str], project: str
) -> None:  # F_Data_13
    group = new_group(api, user, project)
    subgroup = new_subgroup(api, user, project, group["id"], "301-1", 12)
    path = f"/projects/{project}/subgroups/{subgroup['id']}"

    changed = api.patch(path, json={"name": "301-1а"}, headers=user)

    assert changed.json() == subgroup | {"name": "301-1а"}
    assert api.delete(path, headers=user).status_code == 204
    assert api.get(path, headers=user).status_code == 404
    group_now = api.get(f"/projects/{project}/groups/{group['id']}", headers=user).json()
    assert group_now["subgroups"] == []


def test_deleted_group_takes_subgroups_along(
    api: TestClient, user: dict[str, str], project: str
) -> None:
    group = new_group(api, user, project)
    subgroup = new_subgroup(api, user, project, group["id"], "301-1", 12)

    api.delete(f"/projects/{project}/groups/{group['id']}", headers=user)

    assert (
        api.get(f"/projects/{project}/subgroups/{subgroup['id']}", headers=user).status_code == 404
    )



ODD_MONDAY = {"week": "ODD", "day": "MONDAY", "start": "09:00", "end": "13:00"}
EVEN_TUESDAY = {"week": "EVEN", "day": "TUESDAY", "start": "10:00", "end": "15:00"}


def test_group_and_subgroup_availability_crud(
    api: TestClient, user: dict[str, str], project: str
) -> None:
    group_path = f"/projects/{project}/groups"
    subgroup_path = f"/projects/{project}/subgroups"
    group = created(
        api, group_path, user,
        {"name": "301", "student_count": 24, "availability": [EVEN_TUESDAY, ODD_MONDAY]},
    )
    subgroup = created(
        api, subgroup_path, user,
        {
            "group_id": group["id"],
            "name": "301-1",
            "student_count": 12,
            "availability": [ODD_MONDAY],
        },
    )
    other = new_subgroup(api, user, project, group["id"], "301-2", 12)

    assert group["availability"] == [ODD_MONDAY, EVEN_TUESDAY]
    assert subgroup["availability"] == [ODD_MONDAY]

    updated = api.patch(
        f"{subgroup_path}/{subgroup['id']}",
        json={"availability": [EVEN_TUESDAY]},
        headers=user,
    ).json()
    assert updated["availability"] == [EVEN_TUESDAY]

    renamed = api.patch(
        f"{group_path}/{group['id']}", json={"name": "301-А"}, headers=user
    ).json()
    assert renamed["availability"] == [ODD_MONDAY, EVEN_TUESDAY]
    assert renamed["subgroups"] == [
        {"id": subgroup["id"], "name": "301-1", "student_count": 12, "availability": [EVEN_TUESDAY]},
        {"id": other["id"], "name": "301-2", "student_count": 12, "availability": []},
    ]
    assert api.get(f"{subgroup_path}/{subgroup['id']}", headers=user).json()["availability"] == [
        EVEN_TUESDAY
    ]

    cleared = api.patch(
        f"{group_path}/{group['id']}", json={"availability": []}, headers=user
    ).json()
    assert cleared["availability"] == []
    assert cleared["subgroups"][0]["availability"] == [EVEN_TUESDAY]
    assert api.get(group_path, headers=user).json()[0]["availability"] == []

    assert api.patch(
        f"{subgroup_path}/{subgroup['id']}", json={"availability": []}, headers=user
    ).json()["availability"] == []
    assert api.get(f"{subgroup_path}/{other['id']}", headers=user).json()["availability"] == []


def test_availability_rejects_invalid_interval_and_keeps_existing_data(
    api: TestClient, user: dict[str, str], project: str
) -> None:
    group = created(
        api,
        f"/projects/{project}/groups",
        user,
        {"name": "301", "student_count": 24, "availability": [ODD_MONDAY]},
    )
    path = f"/projects/{project}/groups/{group['id']}"
    invalid = ODD_MONDAY | {"end": "08:00"}

    response = api.patch(path, json={"availability": [invalid]}, headers=user)

    assert response.status_code == 422
    assert response.json()["details"]["field"] == "availability.0.end"
    assert api.get(path, headers=user).json()["availability"] == [ODD_MONDAY]

    subgroup = new_subgroup(api, user, project, group["id"], "301-1", 12)
    response = api.patch(
        f"/projects/{project}/subgroups/{subgroup['id']}",
        json={"availability": [invalid]},
        headers=user,
    )
    assert response.status_code == 422
    assert response.json()["details"]["field"] == "availability.0.end"
    assert api.get(
        f"/projects/{project}/subgroups/{subgroup['id']}", headers=user
    ).json()["availability"] == []


def test_availability_is_scoped_to_project(
    api: TestClient, user: dict[str, str], project: str
) -> None:
    foreign = new_project(api, user, "Другой")
    group = new_group(api, user, foreign)
    subgroup = new_subgroup(api, user, foreign, group["id"], "301-1", 12)

    assert api.patch(
        f"/projects/{project}/groups/{group['id']}",
        json={"availability": [ODD_MONDAY]}, headers=user,
    ).status_code == 404
    assert api.patch(
        f"/projects/{project}/subgroups/{subgroup['id']}",
        json={"availability": [ODD_MONDAY]}, headers=user,
    ).status_code == 404
