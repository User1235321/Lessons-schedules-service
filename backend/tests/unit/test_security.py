from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from pydantic import ValidationError

from app.bootstrap.api import create_app
from app.bootstrap.settings import DEV_JWT_SECRET, Settings
from app.domain.auth.errors import InvalidAccessToken
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


def test_access_token_is_read_until_it_expires() -> None:
    tokens = JwtTokenService(SECRET, access_ttl=timedelta(minutes=15))
    user_id = UserId(uuid4())
    token = tokens.issue_access_token(user_id, NOW)

    assert tokens.read_access_token(token, NOW + timedelta(minutes=14, seconds=59)) == user_id
    with pytest.raises(InvalidAccessToken):
        tokens.read_access_token(token, NOW + timedelta(minutes=15))


@pytest.mark.parametrize(
    "claims",
    [
        {"exp": NOW + timedelta(minutes=15)},
        {"sub": "not-a-uuid", "exp": NOW + timedelta(minutes=15)},
    ],
    ids=["no subject", "subject is not an id"],
)
def test_access_token_without_valid_subject_is_rejected(claims: dict[str, object]) -> None:
    tokens = JwtTokenService(SECRET, access_ttl=timedelta(minutes=15))

    with pytest.raises(InvalidAccessToken):
        tokens.read_access_token(jwt.encode(claims, SECRET, algorithm="HS256"), NOW)


def test_access_token_signed_with_other_key_or_unsigned_is_rejected() -> None:
    tokens = JwtTokenService(SECRET, access_ttl=timedelta(minutes=15))
    claims = {"sub": str(uuid4()), "exp": NOW + timedelta(minutes=15)}

    for token in (
        jwt.encode(claims, "another-secret-of-at-least-32-chars", algorithm="HS256"),
        jwt.encode(claims, None, algorithm="none"),
    ):
        with pytest.raises(InvalidAccessToken):
            tokens.read_access_token(token, NOW)


def test_refresh_tokens_are_random_and_their_hash_is_stable() -> None:
    tokens = JwtTokenService(SECRET, access_ttl=timedelta(minutes=15))

    first, second = tokens.new_refresh_token(), tokens.new_refresh_token()

    assert first != second
    assert tokens.hash_refresh_token(first) == tokens.hash_refresh_token(first)
    assert tokens.hash_refresh_token(first) not in (first, tokens.hash_refresh_token(second))


def test_short_jwt_secret_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(jwt_secret="change-me")


def test_development_runs_with_example_key() -> None:
    settings = Settings(_env_file=None, app_env="development", jwt_secret=DEV_JWT_SECRET)

    assert settings.jwt_secret == DEV_JWT_SECRET


@pytest.mark.parametrize(
    "unsafe",
    [{"jwt_secret": DEV_JWT_SECRET}, {"jwt_secret": SECRET, "refresh_cookie_secure": False}],
    ids=["example key", "cookie without secure"],
)
def test_production_refuses_unsafe_settings(unsafe: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="production", **unsafe)


def test_production_runs_with_own_key() -> None:
    settings = Settings(_env_file=None, app_env="production", jwt_secret=SECRET)

    assert settings.jwt_secret == SECRET


def test_server_without_app_env_does_not_start_with_example_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Как на сервере, где забыли настроить окружение: APP_ENV нет, ключ из примера
    monkeypatch.delenv("APP_ENV")
    monkeypatch.setenv("JWT_SECRET", DEV_JWT_SECRET)
    monkeypatch.setattr(Settings, "model_config", {**Settings.model_config, "env_file": None})

    with pytest.raises(ValidationError, match="JWT_SECRET"):
        create_app()
