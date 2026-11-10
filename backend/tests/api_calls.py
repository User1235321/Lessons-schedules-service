from typing import Any

from fastapi.testclient import TestClient


def sign_in(api: TestClient, email: str = "ivan@mail.ru") -> dict[str, str]:
    """Регистрирует пользователя и возвращает заголовок с его access-токеном."""
    response = api.post("/auth/register", json={"email": email, "password": "secret1"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def new_project(api: TestClient, user: dict[str, str], name: str = "Осень") -> str:
    response = api.post("/projects", json={"name": name}, headers=user)
    assert response.status_code == 201
    return response.json()["id"]


def created(
    api: TestClient, path: str, user: dict[str, str], body: dict[str, Any]
) -> dict[str, Any]:
    response = api.post(path, json=body, headers=user)
    assert response.status_code == 201, response.json()
    return response.json()
