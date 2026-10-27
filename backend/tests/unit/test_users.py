from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.auth.session import UserSession
from app.domain.auth.user import Email, check_new_password
from app.domain.shared.errors import InvalidValue
from app.domain.shared.ids import SessionId, UserId

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


def test_email_is_normalized_to_lowercase() -> None:
    assert Email("  Ivan.Petrov@Mail.RU ").value == "ivan.petrov@mail.ru"


def test_same_address_in_different_case_is_equal() -> None:
    assert Email("Ivan@mail.ru") == Email("ivan@MAIL.ru")


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "ivan", "ivan@", "@mail.ru", "ivan@mail", "iv an@mail.ru", "ivan@@mail.ru"],
)
def test_malformed_email_is_rejected(raw: str) -> None:
    with pytest.raises(InvalidValue) as error:
        Email(raw)

    assert error.value.field == "email"


def test_too_long_email_is_rejected() -> None:
    with pytest.raises(InvalidValue):
        Email("a" * 250 + "@x.ru")


@pytest.mark.parametrize("password", ["123456", "x" * 20, "пароль"])
def test_password_of_6_to_20_characters_is_accepted(password: str) -> None:  # F_Auth_2
    check_new_password(password)


@pytest.mark.parametrize("password", ["", "12345", "x" * 21])
def test_password_of_other_length_is_rejected(password: str) -> None:  # F_Auth_2, F_Valid_1
    with pytest.raises(InvalidValue) as error:
        check_new_password(password)

    assert error.value.field == "password"


def open_session(ttl: timedelta = timedelta(days=30)) -> UserSession:
    return UserSession.open(
        session_id=SessionId(uuid4()),
        user_id=UserId(uuid4()),
        refresh_token_hash="hash",
        now=NOW,
        ttl=ttl,
    )


def test_session_is_active_until_it_expires() -> None:
    session = open_session(ttl=timedelta(days=30))

    assert session.expires_at == NOW + timedelta(days=30)
    assert session.is_active(NOW + timedelta(days=29))
    assert not session.is_active(NOW + timedelta(days=30))


def test_revoked_session_is_not_active() -> None:
    session = open_session()

    session.revoke(NOW + timedelta(minutes=5))

    assert not session.is_active(NOW + timedelta(minutes=6))


def test_second_revoke_keeps_first_revocation_time() -> None:
    session = open_session()

    session.revoke(NOW + timedelta(minutes=5))
    session.revoke(NOW + timedelta(minutes=10))

    assert session.revoked_at == NOW + timedelta(minutes=5)
