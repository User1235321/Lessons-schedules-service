from datetime import UTC, datetime, timedelta

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


def refresh(api: TestClient, refresh_token: str) -> Response:
    return api.post("/auth/refresh", json={"refresh_token": refresh_token})


def logout(api: TestClient, refresh_token: str) -> Response:
    return api.post("/auth/logout", json={"refresh_token": refresh_token})


def me(api: TestClient, access_token: str) -> Response:
    return api.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})


class FakeClock:
    """Часы, которые тест переводит вперёд."""

    def __init__(self) -> None:
        self.current = datetime.now(UTC)

    def now(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta


@pytest.fixture
def clock(container: Container) -> FakeClock:
    container.clock = fake = FakeClock()
    return fake


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


def test_refresh_issues_new_pair_and_burns_old_token(api: TestClient) -> None:  # HLD 8
    old = register(api).json()

    response = refresh(api, old["refresh_token"])

    assert response.status_code == 200
    new = response.json()
    assert new["refresh_token"] != old["refresh_token"]
    assert me(api, new["access_token"]).status_code == 200
    assert refresh(api, old["refresh_token"]).status_code == 401
    assert refresh(api, new["refresh_token"]).status_code == 200


def test_unknown_refresh_token_is_rejected(api: TestClient) -> None:
    response = refresh(api, "made-up-token")

    assert response.status_code == 401
    assert response.json() == {
        "code": "INVALID_REFRESH_TOKEN",
        "message": "Сессия завершена, войдите снова",
        "details": {},
    }


def test_refresh_does_not_extend_session(
    api: TestClient, container: Container, clock: FakeClock
) -> None:
    ttl = timedelta(days=container.settings.refresh_token_ttl_days)
    refresh_token = register(api).json()["refresh_token"]

    clock.advance(ttl - timedelta(days=1))
    refresh_token = refresh(api, refresh_token).json()["refresh_token"]
    clock.advance(timedelta(days=1))

    assert refresh(api, refresh_token).status_code == 401


def test_logout_ends_only_its_own_session(api: TestClient) -> None:
    phone = register(api).json()
    laptop = login(api).json()

    assert logout(api, phone["refresh_token"]).status_code == 204

    assert refresh(api, phone["refresh_token"]).status_code == 401
    assert refresh(api, laptop["refresh_token"]).status_code == 200


def test_repeated_or_unknown_logout_succeeds(api: TestClient) -> None:
    refresh_token = register(api).json()["refresh_token"]
    logout(api, refresh_token)

    assert logout(api, refresh_token).status_code == 204
    assert logout(api, "made-up-token").status_code == 204


def test_me_returns_signed_in_user(api: TestClient, container: Container) -> None:
    access_token = register(api, email="Ivan@mail.ru").json()["access_token"]

    response = me(api, access_token)

    assert response.status_code == 200
    user = stored_user(container, "ivan@mail.ru")
    assert response.json() == {"id": str(user.id), "email": "ivan@mail.ru"}


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Basic aXZhbjpzZWNyZXQx"}],
    ids=["no header", "not bearer"],
)
def test_request_without_access_token_is_rejected(
    api: TestClient, headers: dict[str, str]
) -> None:  # NF_Security_1
    response = api.get("/auth/me", headers=headers)

    assert response.status_code == 401
    assert response.json() == {
        "code": "NOT_AUTHENTICATED",
        "message": "Требуется вход в систему",
        "details": {},
    }


def test_forged_or_malformed_access_token_is_rejected(api: TestClient) -> None:
    tokens = register(api).json()
    claims = jwt.decode(tokens["access_token"], options={"verify_signature": False})
    forged = jwt.encode(claims, "someone-elses-secret-of-32-chars", algorithm="HS256")

    for access_token in (forged, "not-a-jwt", tokens["refresh_token"]):
        response = me(api, access_token)
        assert response.status_code == 401
        assert response.json()["code"] == "INVALID_ACCESS_TOKEN"


def test_access_token_expires_after_ttl(
    api: TestClient, container: Container, clock: FakeClock
) -> None:
    ttl = timedelta(minutes=container.settings.access_token_ttl_minutes)
    access_token = register(api).json()["access_token"]

    clock.advance(ttl - timedelta(seconds=1))
    assert me(api, access_token).status_code == 200
    clock.advance(timedelta(seconds=1))

    response = me(api, access_token)
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_ACCESS_TOKEN"
