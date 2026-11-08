from datetime import timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.fakes import FakeClock

DEFAULTS = {  # F_Project_5
    "cycle": {
        "odd_week_days": ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"],
        "even_week_days": ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"],
    },
    "time_mode": {"type": "HOUR_START"},
    "duration_mode": {"type": "UNIFORM", "duration_minutes": 100},
}
CUSTOM = {  # как в test-data/minimal-project.json
    "cycle": {"odd_week_days": ["MONDAY", "TUESDAY"], "even_week_days": ["MONDAY", "TUESDAY"]},
    "time_mode": {"type": "STEP", "step_minutes": 30},
    "duration_mode": {"type": "INDIVIDUAL"},
}


def sign_in(api: TestClient, email: str = "ivan@mail.ru") -> dict[str, str]:
    response = api.post("/auth/register", json={"email": email, "password": "secret1"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create(api: TestClient, user: dict[str, str], **body: Any) -> dict[str, Any]:
    response = api.post("/projects", json={"name": "Осень", **body}, headers=user)
    assert response.status_code == 201
    return response.json()


def settings_of(project: dict[str, Any]) -> dict[str, Any]:
    return {block: project[block] for block in ("cycle", "time_mode", "duration_mode")}


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


def test_project_with_only_name_gets_default_settings(api: TestClient) -> None:  # F_Project_5
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


def test_missing_settings_blocks_get_defaults(api: TestClient) -> None:
    user = sign_in(api)

    project = create(api, user, time_mode={"type": "STEP", "step_minutes": 15})

    assert project["time_mode"] == {"type": "STEP", "step_minutes": 15}
    assert project["cycle"] == DEFAULTS["cycle"]
    assert project["duration_mode"] == DEFAULTS["duration_mode"]


@pytest.mark.parametrize("name", ["", "   "])
def test_project_needs_a_name(api: TestClient, name: str) -> None:  # F_Project_1
    response = api.post("/projects", json={"name": name}, headers=sign_in(api))

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_VALUE"
    assert response.json()["details"] == {"field": "name"}


@pytest.mark.parametrize(
    ("block", "value", "field"),
    [
        ("time_mode", {"type": "STEP"}, "time_mode.step_minutes"),
        ("time_mode", {"type": "HOUR_START", "step_minutes": 30}, "time_mode.step_minutes"),
        (
            "duration_mode",
            {"type": "UNIFORM", "duration_minutes": 0},
            "duration_mode.duration_minutes",
        ),
    ],
    ids=["step missing", "step with hour start", "zero duration"],
)
def test_invalid_setting_names_its_json_path(
    api: TestClient, block: str, value: dict[str, Any], field: str
) -> None:  # F_Valid_1, F_Valid_2
    response = api.post("/projects", json={"name": "Осень", block: value}, headers=sign_in(api))

    assert response.status_code == 422
    assert response.json()["details"] == {"field": field}


def test_unknown_weekday_is_rejected(api: TestClient) -> None:  # F_Valid_2
    cycle = {"odd_week_days": ["MONDAY", "FUNDAY"], "even_week_days": []}

    response = api.post("/projects", json={"name": "Осень", "cycle": cycle}, headers=sign_in(api))

    assert response.status_code == 422
    assert response.json()["details"]["fields"][0]["field"] == "cycle.odd_week_days.1"


def test_empty_week_is_allowed(api: TestClient) -> None:  # F_Valid_3
    cycle = {"odd_week_days": ["SATURDAY", "MONDAY", "MONDAY"], "even_week_days": []}

    project = create(api, sign_in(api), cycle=cycle)

    assert project["cycle"] == {"odd_week_days": ["MONDAY", "SATURDAY"], "even_week_days": []}


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


def test_sent_settings_block_replaces_the_old_one(api: TestClient) -> None:
    user = sign_in(api)
    created = create(api, user, **CUSTOM)

    response = api.patch(
        f"/projects/{created['id']}", json={"time_mode": {"type": "HOUR_START"}}, headers=user
    )

    updated = response.json()
    assert updated["time_mode"] == {"type": "HOUR_START"}  # шаг ушёл вместе со старым блоком
    assert updated["cycle"] == CUSTOM["cycle"]
    assert updated["duration_mode"] == CUSTOM["duration_mode"]
    assert api.get(f"/projects/{created['id']}", headers=user).json() == updated


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
        json={"name": " ", "time_mode": {"type": "STEP", "step_minutes": 30}},
        headers=user,
    )

    assert response.status_code == 422
    assert api.get(f"/projects/{created['id']}", headers=user).json() == created


def test_deleted_project_is_gone(api: TestClient) -> None:  # F_Project_2
    user = sign_in(api)
    doomed, kept = create(api, user, name="Удаляемый"), create(api, user, name="Остаётся")

    response = api.delete(f"/projects/{doomed['id']}", headers=user)

    assert response.status_code == 204
    assert api.get(f"/projects/{doomed['id']}", headers=user).status_code == 404
    assert api.delete(f"/projects/{doomed['id']}", headers=user).status_code == 404
    assert api.get("/projects", headers=user).json() == [kept]
