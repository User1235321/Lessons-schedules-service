from datetime import timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.fakes import FakeClock

DAYS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"]
DEFAULTS = {
    "odd_week_days": DAYS,
    "even_week_days": DAYS,
    "time_mode": "HOUR_START",
    "time_step_minutes": None,
    "duration_mode": "UNIFORM",
    "duration_minutes": 100,
}
CUSTOM = {
    "odd_week_days": ["MONDAY", "TUESDAY"],
    "even_week_days": ["MONDAY", "TUESDAY"],
    "time_mode": "STEP",
    "time_step_minutes": 30,
    "duration_mode": "INDIVIDUAL",
    "duration_minutes": None,
}
SETTINGS_FIELDS = tuple(DEFAULTS)


def sign_in(api: TestClient, email: str = "ivan@mail.ru") -> dict[str, str]:
    response = api.post("/auth/register", json={"email": email, "password": "secret1"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create(api: TestClient, user: dict[str, str], **body: Any) -> dict[str, Any]:
    response = api.post("/projects", json={"name": "Осень", **body}, headers=user)
    assert response.status_code == 201
    return response.json()


def settings_of(project: dict[str, Any]) -> dict[str, Any]:
    return {field: project[field] for field in SETTINGS_FIELDS}


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/projects"),
        ("POST", "/projects"),
        ("GET", f"/projects/{uuid4()}"),
        ("PATCH", f"/projects/{uuid4()}"),
        ("DELETE", f"/projects/{uuid4()}"),
    ],
)
def test_projects_require_sign_in(api: TestClient, method: str, path: str) -> None:  # NF_Security_1
    response = api.request(method, path, json={"name": "Осень"})

    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"


def test_project_with_only_name_gets_default_settings(api: TestClient) -> None:
    user = sign_in(api)

    project = create(api, user, name="  Осень 2026  ")

    assert project["name"] == "Осень 2026"
    assert settings_of(project) == DEFAULTS
    assert project["created_at"] == project["updated_at"]


def test_project_keeps_settings_given_on_creation(api: TestClient) -> None:  # F_Project_4
    user = sign_in(api)
    created = create(api, user, **CUSTOM)

    reopened = api.get(f"/projects/{created['id']}", headers=user).json()

    assert reopened == created
    assert settings_of(reopened) == CUSTOM


def test_missing_settings_fields_get_defaults(api: TestClient) -> None:
    user = sign_in(api)

    project = create(api, user, time_mode="STEP", time_step_minutes=15)

    assert project["time_mode"] == "STEP"
    assert project["time_step_minutes"] == 15
    assert project["odd_week_days"] == DEFAULTS["odd_week_days"]
    assert project["even_week_days"] == DEFAULTS["even_week_days"]
    assert project["duration_mode"] == DEFAULTS["duration_mode"]
    assert project["duration_minutes"] == DEFAULTS["duration_minutes"]


@pytest.mark.parametrize("unknown", ["unexpected", "cycle", "step_minutes"])
def test_post_rejects_unknown_fields(api: TestClient, unknown: str) -> None:
    user = sign_in(api)

    response = api.post("/projects", json={"name": "Осень", unknown: True}, headers=user)

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert response.json()["details"]["fields"][0]["field"] == unknown
    assert api.get("/projects", headers=user).json() == []


@pytest.mark.parametrize("name", ["", "   "])
def test_project_needs_a_name(api: TestClient, name: str) -> None:  # F_Project_1
    response = api.post("/projects", json={"name": name}, headers=sign_in(api))

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_VALUE"
    assert response.json()["details"] == {"field": "name"}


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"time_mode": "STEP"}, "time_step_minutes"),
        ({"time_mode": "HOUR_START", "time_step_minutes": 30}, "time_step_minutes"),
        ({"duration_mode": "UNIFORM", "duration_minutes": 0}, "duration_minutes"),
        ({"duration_mode": "INDIVIDUAL", "duration_minutes": 30}, "duration_minutes"),
    ],
)
def test_invalid_setting_names_its_json_path(
    api: TestClient, changes: dict[str, Any], field: str
) -> None:
    response = api.post("/projects", json={"name": "Осень", **changes}, headers=sign_in(api))

    assert response.status_code == 422
    assert response.json()["details"] == {"field": field}


def test_unknown_weekday_is_rejected(api: TestClient) -> None:
    response = api.post(
        "/projects",
        json={"name": "Осень", "odd_week_days": ["MONDAY", "FUNDAY"]},
        headers=sign_in(api),
    )

    assert response.status_code == 422
    assert response.json()["details"]["fields"][0]["field"] == "odd_week_days.1"


def test_empty_week_is_allowed(api: TestClient) -> None:  # F_Valid_3
    project = create(
        api,
        sign_in(api),
        odd_week_days=["SATURDAY", "MONDAY", "MONDAY"],
        even_week_days=[],
    )

    assert project["odd_week_days"] == ["MONDAY", "SATURDAY"]
    assert project["even_week_days"] == []


def test_list_has_only_own_projects_recently_changed_first(
    api: TestClient, clock: FakeClock
) -> None:  # F_Project_3, NF_Security_2
    ivan, petr = sign_in(api, "ivan@mail.ru"), sign_in(api, "petr@mail.ru")
    first = create(api, ivan, name="Первый")
    clock.advance(timedelta(minutes=1))
    second = create(api, ivan, name="Второй")
    create(api, petr, name="Чужой")
    clock.advance(timedelta(minutes=1))
    api.patch(f"/projects/{first['id']}", json={"name": "Первый, изменён"}, headers=ivan)

    response = api.get("/projects", headers=ivan)

    assert response.status_code == 200
    assert [project["name"] for project in response.json()] == ["Первый, изменён", "Второй"]
    assert response.json()[1] == second


def test_foreign_project_looks_like_missing_one(api: TestClient) -> None:  # NF_Security_2
    ivan, petr = sign_in(api, "ivan@mail.ru"), sign_in(api, "petr@mail.ru")
    path = f"/projects/{create(api, ivan)['id']}"

    for method, body in (("GET", None), ("PATCH", {"name": "Моё"}), ("DELETE", None)):
        foreign = api.request(method, path, json=body, headers=petr)
        missing = api.request(method, f"/projects/{uuid4()}", json=body, headers=petr)
        assert foreign.status_code == missing.status_code == 404
        assert foreign.json()["code"] == missing.json()["code"] == "NOT_FOUND"

    assert api.get(path, headers=ivan).json()["name"] == "Осень"


def test_rename_keeps_settings_and_moves_update_time(api: TestClient, clock: FakeClock) -> None:
    user = sign_in(api)
    created = create(api, user, **CUSTOM)
    clock.advance(timedelta(minutes=5))

    response = api.patch(f"/projects/{created['id']}", json={"name": "Весна"}, headers=user)

    assert response.status_code == 200
    updated = response.json()
    assert updated["name"] == "Весна"
    assert settings_of(updated) == CUSTOM
    assert updated["updated_at"] > created["updated_at"] == updated["created_at"]


def test_patch_preserves_fields_not_sent(api: TestClient) -> None:
    user = sign_in(api)
    created = create(api, user, **CUSTOM)

    response = api.patch(
        f"/projects/{created['id']}",
        json={"odd_week_days": ["FRIDAY"]},
        headers=user,
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["odd_week_days"] == ["FRIDAY"]
    assert {key: updated[key] for key in SETTINGS_FIELDS if key != "odd_week_days"} == {
        key: CUSTOM[key] for key in SETTINGS_FIELDS if key != "odd_week_days"
    }
    assert api.get(f"/projects/{created['id']}", headers=user).json() == updated


def test_patch_can_clear_inactive_mode_parameters(api: TestClient) -> None:
    user = sign_in(api)
    created = create(api, user, **CUSTOM)

    response = api.patch(
        f"/projects/{created['id']}",
        json={"time_mode": "HOUR_START", "time_step_minutes": None},
        headers=user,
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["time_mode"] == "HOUR_START"
    assert updated["time_step_minutes"] is None
    assert updated["even_week_days"] == CUSTOM["even_week_days"]
    assert updated["duration_mode"] == CUSTOM["duration_mode"]


def test_patch_mode_change_without_required_parameter_is_invalid(api: TestClient) -> None:
    user = sign_in(api)
    created = create(api, user, **CUSTOM)

    response = api.patch(
        f"/projects/{created['id']}",
        json={"time_mode": "HOUR_START"},
        headers=user,
    )

    assert response.status_code == 422
    assert response.json()["details"]["field"] == "time_step_minutes"
    assert api.get(f"/projects/{created['id']}", headers=user).json() == created


def test_patch_only_minutes_preserves_mode(api: TestClient) -> None:
    user = sign_in(api)
    created = create(api, user, **CUSTOM)

    response = api.patch(
        f"/projects/{created['id']}",
        json={"time_step_minutes": 45},
        headers=user,
    )

    assert response.status_code == 200
    assert response.json()["time_mode"] == "STEP"
    assert response.json()["time_step_minutes"] == 45
    assert response.json()["duration_mode"] == CUSTOM["duration_mode"]


def test_empty_patch_changes_nothing(api: TestClient, clock: FakeClock) -> None:
    user = sign_in(api)
    created = create(api, user)
    clock.advance(timedelta(minutes=5))

    response = api.patch(f"/projects/{created['id']}", json={}, headers=user)

    assert response.status_code == 200
    assert response.json() == created


def test_invalid_patch_changes_nothing(api: TestClient) -> None:
    user = sign_in(api)
    created = create(api, user)

    response = api.patch(
        f"/projects/{created['id']}",
        json={"name": " ", "time_mode": "STEP", "time_step_minutes": 30},
        headers=user,
    )

    assert response.status_code == 422
    assert api.get(f"/projects/{created['id']}", headers=user).json() == created


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"unexpected": True}, "unexpected"),
        ({"cycle": CUSTOM["odd_week_days"]}, "cycle"),
        ({"time_mode": {"type": "STEP"}}, "time_mode"),
        ({"duration_mode": {"type": "INDIVIDUAL"}}, "duration_mode"),
    ],
)
def test_unknown_patch_field_rejects_all_changes(
    api: TestClient, changes: dict[str, Any], field: str
) -> None:
    user = sign_in(api)
    created = create(api, user, **CUSTOM)
    path = f"/projects/{created['id']}"

    response = api.patch(path, json={"name": "Весна", **changes}, headers=user)

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"] == "Проверьте введённые данные"
    assert [issue["field"] for issue in body["details"]["fields"]] == [field]
    assert all(issue["reason"] for issue in body["details"]["fields"])
    assert api.get(path, headers=user).json() == created


def test_patch_reports_every_unknown_field_without_saving(api: TestClient) -> None:
    user = sign_in(api)
    created = create(api, user, **CUSTOM)
    path = f"/projects/{created['id']}"
    changes = {
        "name": "Весна",
        "unexpected": True,
        "extra_day": True,
        "extra_step": 15,
        "extra_duration": 100,
    }

    response = api.patch(path, json=changes, headers=user)

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert {issue["field"] for issue in response.json()["details"]["fields"]} == {
        "unexpected",
        "extra_day",
        "extra_step",
        "extra_duration",
    }
    assert api.get(path, headers=user).json() == created


def test_deleted_project_is_gone(api: TestClient) -> None:  # F_Project_2
    user = sign_in(api)
    doomed, kept = create(api, user, name="Удаляемый"), create(api, user, name="Остаётся")

    response = api.delete(f"/projects/{doomed['id']}", headers=user)

    assert response.status_code == 204
    assert api.get(f"/projects/{doomed['id']}", headers=user).status_code == 404
    assert api.delete(f"/projects/{doomed['id']}", headers=user).status_code == 404
    assert api.get("/projects", headers=user).json() == [kept]


def test_patch_restores_both_empty_weeks_without_changing_other_settings(
    api: TestClient,
) -> None:
    user = sign_in(api)
    created = create(api, user, **CUSTOM)
    response = api.patch(
        f"/projects/{created['id']}",
        json={"odd_week_days": [], "even_week_days": []},
        headers=user,
    )

    assert response.status_code == 200
    assert response.json()["odd_week_days"] == []
    assert response.json()["even_week_days"] == []
    assert response.json()["time_mode"] == CUSTOM["time_mode"]
    assert response.json()["duration_mode"] == CUSTOM["duration_mode"]
    assert api.get(f"/projects/{created['id']}", headers=user).json() == response.json()


def test_invalid_step_patch_keeps_previous_settings(api: TestClient) -> None:
    user = sign_in(api)
    created = create(api, user, **CUSTOM)

    response = api.patch(
        f"/projects/{created['id']}",
        json={"time_mode": "STEP", "time_step_minutes": 0},
        headers=user,
    )

    assert response.status_code == 422
    assert response.json()["details"]["field"] == "time_step_minutes"
    assert api.get(f"/projects/{created['id']}", headers=user).json() == created


def test_duration_mode_patch_replaces_only_its_block(api: TestClient) -> None:
    user = sign_in(api)
    created = create(api, user, **CUSTOM)

    response = api.patch(
        f"/projects/{created['id']}",
        json={"duration_mode": "UNIFORM", "duration_minutes": 95},
        headers=user,
    )

    assert response.status_code == 200
    assert response.json()["duration_mode"] == "UNIFORM"
    assert response.json()["duration_minutes"] == 95
    assert response.json()["time_mode"] == CUSTOM["time_mode"]
    assert response.json()["odd_week_days"] == CUSTOM["odd_week_days"]
    assert api.get(f"/projects/{created['id']}", headers=user).json() == response.json()


@pytest.mark.parametrize("field", ["odd_week_days", "even_week_days", "time_mode", "duration_mode"])
def test_post_rejects_null_nonnullable_fields(api: TestClient, field: str) -> None:
    user = sign_in(api)

    response = api.post("/projects", json={"name": "Осень", field: None}, headers=user)

    assert response.status_code == 422
    assert response.json()["details"]["fields"][0]["field"] == field


def test_patch_rejects_unknown_fields_without_mutation(api: TestClient) -> None:
    user = sign_in(api)
    project = create(api, user)
    path = f"/projects/{project['id']}"

    response = api.patch(
        path, json={"name": "Весна", "old_mode": {"type": "STEP"}}, headers=user
    )

    assert response.status_code == 422
    assert api.get(path, headers=user).json() == project


def test_patch_rejects_null_name(api: TestClient) -> None:
    user = sign_in(api)
    project = create(api, user)

    response = api.patch(
        f"/projects/{project['id']}",
        json={"name": None},
        headers=user,
    )

    assert response.status_code == 422
    assert response.json()["details"]["fields"][0]["field"] == "name"
    assert api.get(f"/projects/{project['id']}", headers=user).json() == project
