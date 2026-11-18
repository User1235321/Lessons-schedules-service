from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.api_calls import created, new_project, sign_in

CONSTRAINT_TYPES = (
    "MIN_START_TIME",
    "MAX_END_TIME",
    "ALLOWED_DAYS",
    "EVERY_WEEK",
    "CONSECUTIVE",
    "NOT_CONSECUTIVE",
    "MIN_GAP",
    "BEFORE",
    "FIXED_DAY",
    "TIME_RANGE",
)


def endpoint(project: str, resource: str = "constraints") -> str:
    return f"/projects/{project}/{resource}"


def make_group(api: TestClient, user: dict[str, str], project: str) -> dict:
    return created(
        api, endpoint(project, "groups"), user, {"name": "301", "student_count": 20}
    )


def make_workload(api: TestClient, user: dict[str, str], project: str) -> dict:
    subject = created(api, endpoint(project, "subjects"), user, {"name": "Математика"})
    group = make_group(api, user, project)
    return created(
        api,
        endpoint(project, "workloads"),
        user,
        {
            "subject_id": subject["id"],
            "group_id": group["id"],
            "lesson_type": "LECTURE",
            "lesson_format": "ONSITE",
            "occurrences_per_cycle": 2,
            "required_teacher_count": 1,
        },
    )


def constraint_body(
    kind: str, parameters: dict, scope_type: str = "PROJECT", scope_id: str | None = None
) -> dict:
    scope = {"type": scope_type}
    if scope_id is not None:
        scope["id"] = scope_id
    return {"constraint_type": kind, "scope": scope, "parameters": parameters}


@pytest.mark.parametrize("kind", CONSTRAINT_TYPES)
def test_every_constraint_type_can_be_created_read_updated_and_deleted(
    api: TestClient, kind: str
) -> None:
    user = sign_in(api)
    project = new_project(api, user)
    workload = make_workload(api, user, project)
    params = {
        "MIN_START_TIME": {"time": "09:00"},
        "MAX_END_TIME": {"time": "18:00"},
        "ALLOWED_DAYS": {"days": ["MONDAY", "TUESDAY"]},
        "EVERY_WEEK": {},
        "CONSECUTIVE": {"workload_id": workload["id"]},
        "NOT_CONSECUTIVE": {"workload_id": workload["id"]},
        "MIN_GAP": {"workload_id": workload["id"], "minutes": 45},
        "BEFORE": {"workload_id": workload["id"]},
        "FIXED_DAY": {"day": "MONDAY", "week": "ODD"},
        "TIME_RANGE": {
            "windows": [
                {"week": "ODD", "day": "MONDAY", "start": "10:00", "end": "13:00"}
            ]
        },
    }[kind]
    workload_scope = kind in {
        "EVERY_WEEK", "CONSECUTIVE", "NOT_CONSECUTIVE", "MIN_GAP", "BEFORE", "FIXED_DAY"
    }
    scope_type = "WORKLOAD" if workload_scope else "PROJECT"
    scope_id = workload["id"] if workload_scope else None
    path = endpoint(project)
    body = constraint_body(kind, params, scope_type, scope_id)
    item = created(api, path, user, body)

    assert item["constraint_type"] == kind
    assert item["parameters"] == params
    assert api.get(path, headers=user).json() == [item]

    updated = api.patch(
        f"{path}/{item['id']}", json={"parameters": params}, headers=user
    )
    assert updated.status_code == 200
    assert updated.json() == item
    assert api.delete(f"{path}/{item['id']}", headers=user).status_code == 204
    assert api.get(path, headers=user).json() == []
    assert api.delete(f"{path}/{item['id']}", headers=user).status_code == 404


def test_constraint_patch_revalidates_full_result_and_preserves_saved_value(
    api: TestClient,
) -> None:
    user = sign_in(api)
    project = new_project(api, user)
    path = endpoint(project)
    item = created(api, path, user, constraint_body("MIN_START_TIME", {"time": "09:00"}))
    invalid = api.patch(
        f"{path}/{item['id']}", json={"constraint_type": "MIN_GAP"}, headers=user
    )
    assert invalid.status_code == 422
    assert api.get(path, headers=user).json() == [item]

    valid = api.patch(
        f"{path}/{item['id']}",
        json={"constraint_type": "MAX_END_TIME", "parameters": {"time": "17:00"}},
        headers=user,
    )
    assert valid.status_code == 200
    assert valid.json()["constraint_type"] == "MAX_END_TIME"
    assert valid.json()["parameters"] == {"time": "17:00"}


@pytest.mark.parametrize(
    ("kind", "params", "scope"),
    [
        ("MIN_START_TIME", {"time": "25:00"}, {"type": "PROJECT"}),
        ("MIN_START_TIME", {"time": "10:00"}, {"type": "GROUP", "id": str(uuid4())}),
        ("ALLOWED_DAYS", {"days": []}, {"type": "PROJECT"}),
        ("EVERY_WEEK", {}, {"type": "PROJECT"}),
        ("MIN_GAP", {"workload_id": str(uuid4()), "minutes": 15}, {"type": "WORKLOAD", "id": str(uuid4())}),
        ("TIME_RANGE", {"windows": [{"week": "ODD", "day": "MONDAY", "start": "14:00", "end": "13:00"}]}, {"type": "PROJECT"}),
    ],
)
def test_invalid_constraint_is_rejected(
    api: TestClient, kind: str, params: dict, scope: dict
) -> None:
    user = sign_in(api)
    project = new_project(api, user)
    response = api.post(
        endpoint(project),
        json={"constraint_type": kind, "scope": scope, "parameters": params},
        headers=user,
    )

    assert response.status_code == 422
    assert api.get(endpoint(project), headers=user).json() == []


def test_constraint_scope_and_related_workload_must_belong_to_project(
    api: TestClient,
) -> None:
    user = sign_in(api)
    owner_project = new_project(api, user, "Первый")
    foreign_project = new_project(api, user, "Второй")
    foreign_workload = make_workload(api, user, foreign_project)
    own_workload = make_workload(api, user, owner_project)
    path = endpoint(owner_project)
    foreign_scope = api.post(
        path,
        headers=user,
        json=constraint_body(
            "EVERY_WEEK", {}, "WORKLOAD", foreign_workload["id"]
        ),
    )
    foreign_related = api.post(
        path,
        headers=user,
        json=constraint_body(
            "BEFORE", {"workload_id": foreign_workload["id"]},
            "WORKLOAD", own_workload["id"],
        ),
    )
    assert foreign_scope.status_code == 422
    assert foreign_related.status_code == 422


def test_constraint_ownership_is_enforced(api: TestClient) -> None:
    owner = sign_in(api, f"{uuid4()}@example.org")
    stranger = sign_in(api, f"{uuid4()}@example.org")
    project = new_project(api, owner)
    path = endpoint(project)
    item = created(api, path, owner, constraint_body("MIN_START_TIME", {"time": "09:00"}))

    assert api.get(path).status_code == 401
    assert api.get(path, headers=stranger).status_code == 404
    assert api.post(
        path, headers=stranger, json=constraint_body("MIN_START_TIME", {"time": "09:00"})
    ).status_code == 404
    assert api.patch(
        f"{path}/{item['id']}", headers=stranger, json={"parameters": {"time": "10:00"}}
    ).status_code == 404
    assert api.delete(f"{path}/{item['id']}", headers=stranger).status_code == 404
    assert api.patch(f"{path}/{uuid4()}", headers=owner, json={}).status_code == 404


@pytest.mark.parametrize("resource", ["GROUP", "SUBGROUP", "STREAM", "WORKLOAD"])
def test_referenced_resources_cannot_be_deleted(api: TestClient, resource: str) -> None:
    user = sign_in(api)
    project = new_project(api, user)
    group = make_group(api, user, project)
    if resource == "GROUP":
        target = group
        path = endpoint(project, "groups")
    elif resource == "SUBGROUP":
        target = created(
            api, endpoint(project, "subgroups"), user,
            {"group_id": group["id"], "name": "301-1", "student_count": 10},
        )
        path = endpoint(project, "subgroups")
    elif resource == "STREAM":
        target = created(
            api, endpoint(project, "streams"), user,
            {"name": "Поток", "group_ids": [group["id"]]},
        )
        path = endpoint(project, "streams")
    else:
        subject = created(api, endpoint(project, "subjects"), user, {"name": "Физика"})
        target = created(
            api, endpoint(project, "workloads"), user,
            {
                "subject_id": subject["id"],
                "group_id": group["id"],
                "lesson_type": "LAB",
                "lesson_format": "ONSITE",
                "occurrences_per_cycle": 2,
                "required_teacher_count": 2,
            },
        )
        path = endpoint(project, "workloads")
    created(
        api, endpoint(project), user,
        constraint_body("MIN_START_TIME", {"time": "10:00"}, resource, target["id"]),
    )

    response = api.delete(f"{path}/{target['id']}", headers=user)

    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"
    assert response.json()["details"]["constraints"]
    assert api.get(f"{path}/{target['id']}", headers=user).status_code == 200


def test_group_deletion_checks_its_subgroup_constraints(api: TestClient) -> None:
    user = sign_in(api)
    project = new_project(api, user)
    group = make_group(api, user, project)
    subgroup = created(
        api, endpoint(project, "subgroups"), user,
        {"group_id": group["id"], "name": "301-1", "student_count": 10},
    )
    created(
        api, endpoint(project), user,
        constraint_body("ALLOWED_DAYS", {"days": ["MONDAY"]}, "SUBGROUP", subgroup["id"]),
    )

    response = api.delete(f"{endpoint(project, 'groups')}/{group['id']}", headers=user)
    assert response.status_code == 409


def test_related_workload_prevents_deletion(api: TestClient) -> None:
    user = sign_in(api)
    project = new_project(api, user)
    first = make_workload(api, user, project)
    second = created(
        api, endpoint(project, "workloads"), user,
        {
            "subject_id": first["subject_id"],
            "group_id": first["group_id"],
            "lesson_type": "PRACTICE",
            "lesson_format": "ONSITE",
            "occurrences_per_cycle": 2,
            "required_teacher_count": 1,
        },
    )
    created(
        api, endpoint(project), user,
        constraint_body(
            "BEFORE", {"workload_id": second["id"]}, "WORKLOAD", first["id"]
        ),
    )

    assert api.delete(
        f"{endpoint(project, 'workloads')}/{second['id']}", headers=user
    ).status_code == 409
