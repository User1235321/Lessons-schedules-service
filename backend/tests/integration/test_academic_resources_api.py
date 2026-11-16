from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.api_calls import created, new_project, sign_in


def path(project_id: str, resource: str) -> str:
    return f"/projects/{project_id}/{resource}"


def subject(api: TestClient, user: dict[str, str], project_id: str) -> dict:
    return created(api, path(project_id, "subjects"), user, {"name": "Физика"})


def group(api: TestClient, user: dict[str, str], project_id: str, name: str) -> dict:
    return created(
        api,
        path(project_id, "groups"),
        user,
        {"name": name, "student_count": 20},
    )


def room_payload(subject_id: str | None = None) -> dict:
    return {
        "name": "Аудитория 1",
        "capacity": 60,
        "room_type": "PRACTICE_SPECIALIZED" if subject_id else "LECTURE",
        "availability": [
            {"week": "ODD", "weekday": "MONDAY", "start_time": "09:00", "end_time": "12:00"}
        ],
        "capabilities": (
            [{"subject_id": subject_id, "lesson_type": "PRACTICE"}] if subject_id else []
        ),
    }


def workload_payload(subject_id: str, target_key: str, target_id: str) -> dict:
    return {
        "subject_id": subject_id,
        "lesson_type": "LECTURE",
        "lesson_format": "ONSITE",
        "occurrences_per_cycle": 2,
        "duration_minutes": None,
        "required_teacher_count": 1,
        target_key: target_id,
    }


def test_rooms_lifecycle_and_capabilities(api: TestClient) -> None:
    user = sign_in(api)
    project_id = new_project(api, user)
    physics = subject(api, user, project_id)
    endpoint = path(project_id, "rooms")
    room = created(api, endpoint, user, room_payload(physics["id"]))

    assert room["room_type"] == "PRACTICE_SPECIALIZED"
    assert len(room["capabilities"]) == 1
    assert room["availability"][0]["weekday"] == "MONDAY"
    assert api.get(endpoint, headers=user).json() == [room]
    assert api.get(f"{endpoint}/{room['id']}", headers=user).json() == room

    updated = api.patch(
        f"{endpoint}/{room['id']}",
        json={"room_type": "LABORATORY", "capacity": 30},
        headers=user,
    )
    assert updated.status_code == 200
    assert updated.json()["capacity"] == 30
    assert updated.json()["capabilities"] == room["capabilities"]

    cleared = api.patch(
        f"{endpoint}/{room['id']}",
        json={"room_type": "LECTURE", "capabilities": []},
        headers=user,
    )
    assert cleared.status_code == 200
    assert cleared.json()["capabilities"] == []
    assert api.delete(f"{endpoint}/{room['id']}", headers=user).status_code == 204
    assert api.get(f"{endpoint}/{room['id']}", headers=user).status_code == 404


def test_rooms_reject_invalid_values_and_duplicate_names(api: TestClient) -> None:
    user = sign_in(api)
    project_id = new_project(api, user)
    endpoint = path(project_id, "rooms")
    created(api, endpoint, user, room_payload())

    duplicate = api.post(endpoint, json={**room_payload(), "name": "аУдИтОрИя 1"}, headers=user)
    invalid_capacity = api.post(
        endpoint, json={**room_payload(), "capacity": 0}, headers=user
    )
    invalid_interval = api.post(
        endpoint,
        json={
            **room_payload(),
            "availability": [
                {
                    "week": "EVEN",
                    "weekday": "MONDAY",
                    "start_time": "12:00",
                    "end_time": "09:00",
                }
            ],
        },
        headers=user,
    )
    invalid_capabilities = api.post(
        endpoint,
        json={
            **room_payload(),
            "capabilities": [{"subject_id": str(uuid4()), "lesson_type": "LECTURE"}],
        },
        headers=user,
    )
    unknown_property = api.post(
        endpoint, json={**room_payload(), "unexpected": True}, headers=user
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "ROOM_NAME_TAKEN"
    assert invalid_capacity.status_code == 422
    assert invalid_capacity.json()["details"]["field"] == "capacity"
    assert invalid_interval.status_code == 422
    assert invalid_interval.json()["details"]["field"] == "availability.0.end_time"
    assert invalid_capabilities.status_code == 422
    assert invalid_capabilities.json()["details"]["field"] == "capabilities"
    assert unknown_property.status_code == 422
    assert unknown_property.json()["details"]["fields"][0]["field"] == "unexpected"


def test_streams_lifecycle_and_group_membership(api: TestClient) -> None:
    user = sign_in(api)
    project_id = new_project(api, user)
    first = group(api, user, project_id, "301")
    second = group(api, user, project_id, "302")
    endpoint = path(project_id, "streams")
    stream = created(
        api, endpoint, user, {"name": "Поток 1", "group_ids": [first["id"]]}
    )
    assert stream["group_ids"] == [first["id"]]
    assert api.get(endpoint, headers=user).json() == [stream]

    updated = api.patch(
        f"{endpoint}/{stream['id']}",
        json={"group_ids": [second["id"], first["id"], first["id"]]},
        headers=user,
    )
    assert updated.status_code == 200
    assert set(updated.json()["group_ids"]) == {first["id"], second["id"]}
    assert len(updated.json()["group_ids"]) == 2

    unknown = api.patch(
        f"{endpoint}/{stream['id']}",
        json={"group_ids": [str(uuid4())]},
        headers=user,
    )
    empty = api.patch(
        f"{endpoint}/{stream['id']}", json={"group_ids": []}, headers=user
    )
    assert unknown.status_code == 422
    assert unknown.json()["details"]["field"] == "group_ids.0"
    assert empty.status_code == 422
    assert empty.json()["details"]["field"] == "group_ids"

    assert api.delete(f"{endpoint}/{stream['id']}", headers=user).status_code == 204
    assert api.get(f"{endpoint}/{stream['id']}", headers=user).status_code == 404


def test_workloads_support_all_targets_formats_and_duration(api: TestClient) -> None:
    user = sign_in(api)
    project_id = new_project(api, user)
    physics = subject(api, user, project_id)
    students = group(api, user, project_id, "301")
    subgroup = created(
        api,
        path(project_id, "subgroups"),
        user,
        {"group_id": students["id"], "name": "301-1", "student_count": 10},
    )
    stream = created(
        api,
        path(project_id, "streams"),
        user,
        {"name": "Поток", "group_ids": [students["id"]]},
    )
    endpoint = path(project_id, "workloads")
    first = created(
        api, endpoint, user, workload_payload(physics["id"], "group_id", students["id"])
    )
    second = created(
        api, endpoint, user, workload_payload(physics["id"], "subgroup_id", subgroup["id"])
    )
    third = created(
        api,
        endpoint,
        user,
        {
            **workload_payload(physics["id"], "stream_id", stream["id"]),
            "lesson_type": "LAB",
            "lesson_format": "REMOTE",
            "required_teacher_count": 3,
            "duration_minutes": 85,
        },
    )

    assert len(api.get(endpoint, headers=user).json()) == 3
    assert first["group_id"] == students["id"]
    assert second["subgroup_id"] == subgroup["id"]
    assert third["stream_id"] == stream["id"]
    assert third["lesson_format"] == "REMOTE"
    assert third["required_teacher_count"] == 3
    assert third["duration_minutes"] == 85

    updated = api.patch(
        f"{endpoint}/{first['id']}",
        json={"subgroup_id": subgroup["id"], "duration_minutes": 90},
        headers=user,
    )
    assert updated.status_code == 200
    assert updated.json()["group_id"] is None
    assert updated.json()["subgroup_id"] == subgroup["id"]
    assert updated.json()["duration_minutes"] == 90

    cleared = api.patch(
        f"{endpoint}/{first['id']}", json={"duration_minutes": None}, headers=user
    )
    assert cleared.status_code == 200
    assert cleared.json()["duration_minutes"] is None
    assert api.delete(f"{endpoint}/{third['id']}", headers=user).status_code == 204


def test_workloads_reject_invalid_numbers_targets_and_references(api: TestClient) -> None:
    user = sign_in(api)
    project_id = new_project(api, user)
    physics = subject(api, user, project_id)
    students = group(api, user, project_id, "301")
    endpoint = path(project_id, "workloads")
    body = workload_payload(physics["id"], "group_id", students["id"])

    invalid_counts = [
        {"occurrences_per_cycle": 0},
        {"duration_minutes": -1},
        {"required_teacher_count": 0},
        {"required_teacher_count": 2},
    ]
    for changes in invalid_counts:
        response = api.post(endpoint, json={**body, **changes}, headers=user)
        assert response.status_code == 422
        assert response.json()["details"]["field"] in changes

    conflicting = api.post(
        endpoint, json={**body, "stream_id": str(uuid4())}, headers=user
    )
    unknown_subject = api.post(
        endpoint, json={**body, "subject_id": str(uuid4())}, headers=user
    )
    unknown_target = api.post(
        endpoint, json={**body, "group_id": str(uuid4())}, headers=user
    )
    assert conflicting.status_code == 422
    assert unknown_subject.json()["details"]["field"] == "subject_id"
    assert unknown_target.json()["details"]["field"] == "group_id"


def test_referenced_stream_cannot_be_deleted(api: TestClient) -> None:
    user = sign_in(api)
    project_id = new_project(api, user)
    physics = subject(api, user, project_id)
    students = group(api, user, project_id, "301")
    streams = path(project_id, "streams")
    stream = created(
        api, streams, user, {"name": "Поток", "group_ids": [students["id"]]}
    )
    created(
        api,
        path(project_id, "workloads"),
        user,
        workload_payload(physics["id"], "stream_id", stream["id"]),
    )

    result = api.delete(f"{streams}/{stream['id']}", headers=user)
    assert result.status_code == 409
    assert result.json()["code"] == "STREAM_IN_USE"
    assert len(result.json()["details"]["workloads"]) == 1


@pytest.mark.parametrize("resource", ["rooms", "streams", "workloads"])
def test_new_resources_require_auth_and_hide_other_projects(
    api: TestClient, resource: str
) -> None:
    owner = sign_in(api, "owner@university.test")
    outsider = sign_in(api, "outsider@university.test")
    project_id = new_project(api, owner)
    endpoint = path(project_id, resource)

    assert api.get(endpoint).status_code == 401
    response = api.get(endpoint, headers=outsider)
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_cross_project_links_are_rejected(api: TestClient) -> None:
    user = sign_in(api)
    first = new_project(api, user, "Проект 1")
    second = new_project(api, user, "Проект 2")
    other_subject = subject(api, user, second)
    other_group = group(api, user, second, "301")

    room = api.post(
        path(first, "rooms"), json=room_payload(other_subject["id"]), headers=user
    )
    stream = api.post(
        path(first, "streams"),
        json={"name": "Поток", "group_ids": [other_group["id"]]},
        headers=user,
    )
    workload = api.post(
        path(first, "workloads"),
        json=workload_payload(other_subject["id"], "group_id", other_group["id"]),
        headers=user,
    )

    assert room.status_code == 422
    assert room.json()["details"]["field"] == "capabilities.0.subject_id"
    assert stream.status_code == 422
    assert stream.json()["details"]["field"] == "group_ids.0"
    assert workload.status_code == 422
    assert workload.json()["details"]["field"] == "subject_id"


@pytest.mark.parametrize(
    "room_type",
    ["LECTURE", "PRACTICE_UNIVERSAL", "PRACTICE_SPECIALIZED", "LABORATORY"],
)
def test_each_room_type_is_supported(api: TestClient, room_type: str) -> None:
    user = sign_in(api)
    project_id = new_project(api, user)
    room = created(
        api,
        path(project_id, "rooms"),
        user,
        {**room_payload(), "room_type": room_type},
    )
    assert room["room_type"] == room_type
