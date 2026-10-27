from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from pydantic import ValidationError

from app.bootstrap.settings import Settings
from app.domain.shared.ids import UserId
from app.infrastructure.security import Argon2PasswordHasher, JwtTokenService

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
SECRET = "test-secret-of-at-least-32-chars"


def test_password_hash_is_salted_argon2id() -> None:  # HLD 8
    hasher = Argon2PasswordHasher()

    first, second = hasher.hash("secret1"), hasher.hash("secret1")

    assert first.startswith("$argon2id$")
    assert first != second


def test_password_is_checked_against_its_hash() -> None:
    hasher = Argon2PasswordHasher()
    password_hash = hasher.hash("пароль")

    assert hasher.verify("пароль", password_hash)
    assert not hasher.verify("Пароль", password_hash)


def test_access_token_names_user_and_expires_after_ttl() -> None:
    tokens = JwtTokenService(SECRET, access_ttl=timedelta(minutes=15))
    user_id = UserId(uuid4())

    token = tokens.issue_access_token(user_id, NOW)

    # NOW уже в прошлом, поэтому срок здесь не проверяем, а сравниваем
    claims = jwt.decode(token, SECRET, algorithms=["HS256"], options={"verify_exp": False})
    assert claims == {
        "sub": str(user_id),
        "iat": int(NOW.timestamp()),
        "exp": int((NOW + timedelta(minutes=15)).timestamp()),
    }


def test_refresh_tokens_are_random_and_their_hash_is_stable() -> None:
    tokens = JwtTokenService(SECRET, access_ttl=timedelta(minutes=15))

    first, second = tokens.new_refresh_token(), tokens.new_refresh_token()

    assert first != second
    assert tokens.hash_refresh_token(first) == tokens.hash_refresh_token(first)
    assert tokens.hash_refresh_token(first) not in (first, tokens.hash_refresh_token(second))


def test_short_jwt_secret_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(jwt_secret="change-me")
