import jwt
import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from app.bootstrap.container import Container
from app.domain.auth.user import Email, User


def register(api: TestClient, email: str = "ivan@mail.ru", password: str = "secret1") -> Response:
    return api.post("/auth/register", json={"email": email, "password": password})


def login(api: TestClient, email: str = "ivan@mail.ru", password: str = "secret1") -> Response:
    return api.post("/auth/login", json={"email": email, "password": password})


def stored_user(container: Container, email: str) -> User:
    with container.uow() as uow:
        user = uow.users.get_by_email(Email(email))
    assert user is not None
    return user


def token_owner(container: Container, access_token: str) -> str:
    claims = jwt.decode(access_token, container.settings.jwt_secret, algorithms=["HS256"])
    return claims["sub"]


def test_register_creates_user_and_signs_in(api: TestClient, container: Container) -> None:
    response = register(api, email="Ivan@Mail.ru")  # F_Auth_1

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    user = stored_user(container, "ivan@mail.ru")
    assert token_owner(container, body["access_token"]) == str(user.id)


def test_password_and_refresh_token_are_stored_as_hashes(
    api: TestClient, container: Container
) -> None:  # HLD 8
    refresh_token = register(api, password="secret1").json()["refresh_token"]

    user = stored_user(container, "ivan@mail.ru")
    with container.uow() as uow:
        session = uow.user_sessions.get_by_token_hash(
            container.tokens.hash_refresh_token(refresh_token)
        )
    assert user.password_hash.startswith("$argon2id$")
    assert session is not None
    assert session.user_id == user.id


def test_email_is_registered_only_once_in_any_case(api: TestClient) -> None:  # F_Auth_3
    register(api, email="ivan@mail.ru")

    response = register(api, email="IVAN@mail.ru")

    assert response.status_code == 409
    assert response.json() == {
        "code": "EMAIL_ALREADY_REGISTERED",
        "message": "Этот адрес уже зарегистрирован",
        "details": {"field": "email"},
    }


@pytest.mark.parametrize("password", ["12345", "x" * 21])
def test_register_rejects_password_of_wrong_length(
    api: TestClient, password: str
) -> None:  # F_Auth_2, F_Valid_1
    response = register(api, password=password)

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_VALUE"
    assert response.json()["details"] == {"field": "password"}


def test_register_rejects_malformed_email(api: TestClient) -> None:  # F_Valid_2
    response = register(api, email="ivan")

    assert response.status_code == 422
    assert response.json()["details"] == {"field": "email"}


def test_missing_field_is_named(api: TestClient) -> None:  # F_Valid_2
    response = api.post("/auth/register", json={"email": "ivan@mail.ru"})

    assert response.status_code == 422
    assert response.json()["details"]["fields"][0]["field"] == "password"


def test_login_opens_new_session(api: TestClient, container: Container) -> None:  # F_Auth_4
    registered = register(api).json()

    response = login(api, email="Ivan@mail.ru")

    assert response.status_code == 200
    body = response.json()
    assert body["refresh_token"] != registered["refresh_token"]
    user = stored_user(container, "ivan@mail.ru")
    assert token_owner(container, body["access_token"]) == str(user.id)


@pytest.mark.parametrize(
    ("email", "password"),
    [("ivan@mail.ru", "wrong-password"), ("petr@mail.ru", "secret1")],
    ids=["wrong password", "unknown email"],
)
def test_login_rejects_wrong_credentials_alike(
    api: TestClient, email: str, password: str
) -> None:  # F_Auth_5
    register(api)

    response = login(api, email=email, password=password)

    assert response.status_code == 401
    assert response.json() == {
        "code": "INVALID_CREDENTIALS",
        "message": "Неверный адрес электронной почты или пароль",
        "details": {},
    }
