import pytest
from fastapi.testclient import TestClient

from app.application.auth.ports import PasswordHasher
from app.bootstrap.container import Container
from app.domain.auth.user import Email


class SpyHasher:
    """Настоящий Argon2, который запоминает, с какими хешами сверял пароль."""

    def __init__(self, real: PasswordHasher) -> None:
        self._real = real
        self.dummy_hash = real.dummy_hash
        self.checked_hashes: list[str] = []

    def hash(self, password: str) -> str:
        return self._real.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        self.checked_hashes.append(password_hash)
        return self._real.verify(password, password_hash)


@pytest.fixture
def spy(container: Container) -> SpyHasher:
    container.passwords = spy = SpyHasher(container.passwords)
    return spy


def login(api: TestClient, email: str, password: str) -> tuple[int, object]:
    response = api.post("/auth/login", json={"email": email, "password": password})
    return response.status_code, response.json()


def test_unknown_email_costs_the_same_argon2_check(
    api: TestClient, container: Container, spy: SpyHasher
) -> None:  # F_Auth_5
    api.post("/auth/register", json={"email": "ivan@mail.ru", "password": "secret1"})
    with container.uow() as uow:
        user = uow.users.get_by_email(Email("ivan@mail.ru"))
    assert user is not None

    wrong_password = login(api, "ivan@mail.ru", "wrong-password")
    unknown_email = login(api, "petr@mail.ru", "secret1")

    assert wrong_password == unknown_email
    assert wrong_password[0] == 401
    assert spy.checked_hashes == [user.password_hash, spy.dummy_hash]


def test_dummy_hash_has_parameters_of_real_ones(container: Container) -> None:
    real = container.passwords.hash("secret1")
    dummy = container.passwords.dummy_hash

    # $argon2id$v=19$m=65536,t=3,p=4$<соль>$<хеш>: время проверки задают параметры
    assert dummy.rsplit("$", 2)[0] == real.rsplit("$", 2)[0]
    assert not container.passwords.verify("secret1", dummy)
