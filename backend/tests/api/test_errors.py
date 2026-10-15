from fastapi import APIRouter, Query
from fastapi.testclient import TestClient

from app.domain.shared.errors import AlreadyExists, InvalidValue, NotFound
from app.main import create_app


def make_client() -> TestClient:
    app = create_app()
    router = APIRouter()

    @router.get("/_test/not-found")
    def not_found() -> None:
        raise NotFound("Проект не найден", project_id="p-1")

    @router.get("/_test/already-exists")
    def already_exists() -> None:
        raise AlreadyExists("Адрес уже зарегистрирован")

    @router.get("/_test/invalid-value")
    def invalid_value() -> None:
        raise InvalidValue("Вместимость должна быть положительной", field="capacity")

    @router.get("/_test/query")
    def query(top_n: int = Query(ge=1)) -> dict[str, int]:
        return {"top_n": top_n}

    @router.get("/_test/crash")
    def crash() -> None:
        raise RuntimeError("boom")

    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def test_not_found_uses_unified_format() -> None:
    response = make_client().get("/_test/not-found")

    assert response.status_code == 404
    assert response.json() == {
        "code": "NOT_FOUND",
        "message": "Проект не найден",
        "details": {"project_id": "p-1"},
    }


def test_already_exists_is_conflict() -> None:
    response = make_client().get("/_test/already-exists")

    assert response.status_code == 409
    assert response.json()["code"] == "ALREADY_EXISTS"


def test_invalid_value_names_the_field() -> None:  # F_Valid_1, F_Valid_2
    response = make_client().get("/_test/invalid-value")

    assert response.status_code == 422
    assert response.json() == {
        "code": "INVALID_VALUE",
        "message": "Вместимость должна быть положительной",
        "details": {"field": "capacity"},
    }


def test_request_validation_error_lists_fields() -> None:  # F_Valid_2
    response = make_client().get("/_test/query", params={"top_n": 0})

    body = response.json()
    assert response.status_code == 422
    assert body["code"] == "VALIDATION_ERROR"
    assert [error["field"] for error in body["details"]["fields"]] == ["top_n"]


def test_unexpected_error_hides_details() -> None:
    response = make_client().get("/_test/crash")

    assert response.status_code == 500
    assert response.json() == {
        "code": "INTERNAL_ERROR",
        "message": "Внутренняя ошибка сервера",
        "details": {},
    }
