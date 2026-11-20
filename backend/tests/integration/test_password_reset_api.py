import hashlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import Engine, delete, select

from app.bootstrap.api import create_app
from app.bootstrap.container import Container, build_container
from app.bootstrap.settings import Settings
from app.domain.shared.ids import UserId
from app.infrastructure.persistence.database import create_session_factory
from app.infrastructure.persistence.models import PasswordResetTokenRow, UserRow
from app.infrastructure.persistence.repositories.users import SqlPasswordResetRepository
from tests.database import wait_for_lock_waiters
from tests.fakes import FakeClock, FakeMailSender

EMAIL = "student@example.org"
OLD_PASSWORD = "secret1"
WEB_ORIGIN = "https://schedules.example.org"


@pytest.fixture
def mail(container: Container, monkeypatch: pytest.MonkeyPatch) -> FakeMailSender:
    monkeypatch.setenv("PASSWORD_RESET_BASE_URL", WEB_ORIGIN)
    container.settings = Settings()
    sender = FakeMailSender()
    container.mail_sender = sender
    return sender


def register(api: TestClient, email: str = EMAIL) -> None:
    response = api.post("/auth/register", json={"email": email, "password": OLD_PASSWORD})
    assert response.status_code == 201


def request_reset(api: TestClient, email: str = EMAIL) -> Response:
    return api.post("/auth/password-reset/request", json={"email": email})


def token_from_mail(mail: FakeMailSender, email: str = EMAIL) -> str:
    recipient, subject, body = mail.messages[-1]
    assert recipient.value == email
    assert subject
    link = urlsplit(next(line for line in body.splitlines() if line.startswith(WEB_ORIGIN)))
    assert link.netloc == "schedules.example.org"
    assert link.path == "/password-reset/confirm"
    return parse_qs(link.fragment)["token"][0]


def confirm(api: TestClient, token: str, password: str = "new-secret") -> Response:
    return api.post("/auth/password-reset/confirm", json={"token": token, "password": password})


def login(api: TestClient, password: str, email: str = EMAIL) -> Response:
    return api.post("/auth/login", json={"email": email, "password": password})


def test_password_reset_from_email_allows_login_with_new_password(
    api: TestClient, mail: FakeMailSender, container: Container
) -> None:
    register(api)
    register(api, "other@example.org")

    with container.session_factory() as session:
        hashes = dict(session.execute(select(UserRow.email, UserRow.password_hash)).all())

    guest = TestClient(api.app, base_url=str(api.base_url), headers={"Host": "untrusted.example"})
    request = request_reset(guest, " Student@EXAMPLE.org ")
    assert request.status_code == 202
    token = token_from_mail(mail)
    assert token not in request.text

    with container.session_factory() as session:
        stored = session.scalar(select(PasswordResetTokenRow))
        assert stored is not None
        assert stored.token_hash == hashlib.sha256(token.encode()).hexdigest()
        owner = session.get(UserRow, stored.user_id)
        assert owner is not None and owner.email == EMAIL

    response = confirm(guest, token)
    assert response.status_code == 204
    assert response.content == b""
    assert "set-cookie" not in response.headers
    assert confirm(guest, token).status_code == 401

    browser = TestClient(api.app, base_url=str(api.base_url))
    assert login(browser, "new-secret").status_code == 200
    assert login(browser, OLD_PASSWORD).status_code == 401
    with container.session_factory() as session:
        updated = dict(session.execute(select(UserRow.email, UserRow.password_hash)).all())
        assert updated[EMAIL].startswith("$argon2id$")
        assert updated[EMAIL] != hashes[EMAIL]
        assert updated["other@example.org"] == hashes["other@example.org"]


def test_request_does_not_disclose_account_existence(
    api: TestClient, mail: FakeMailSender, container: Container
) -> None:
    register(api)
    unknown = request_reset(api, "nobody@example.org")
    assert not mail.messages
    with container.session_factory() as session:
        assert session.scalar(select(PasswordResetTokenRow)) is None

    known = request_reset(api)
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert set(known.json()) == {"message"}
    assert len(mail.messages) == 1

    invalid = request_reset(api, "bad-address")
    assert invalid.status_code == 422
    assert invalid.json()["details"] == {"field": "email"}


@pytest.mark.parametrize(("invalid", "valid"), [("x" * 5, " абвг "), ("x" * 21, "я" * 20)])
def test_password_length_validation_preserves_token(
    api: TestClient, mail: FakeMailSender, invalid: str, valid: str
) -> None:
    register(api)
    assert request_reset(api).status_code == 202
    token = token_from_mail(mail)

    response = confirm(api, token, invalid)
    assert response.status_code == 422
    assert response.json()["details"] == {"field": "password"}
    assert login(api, OLD_PASSWORD).status_code == 200
    assert confirm(api, token, valid).status_code == 204
    assert login(api, valid).status_code == 200


def test_unknown_and_expired_tokens_have_the_same_error(
    api: TestClient, mail: FakeMailSender, clock: FakeClock, container: Container
) -> None:
    register(api)
    assert request_reset(api).status_code == 202
    token = token_from_mail(mail)
    clock.advance(timedelta(minutes=container.settings.password_reset_token_ttl_minutes))

    expired = confirm(api, token)
    unknown = confirm(api, "unknown")
    assert expired.status_code == unknown.status_code == 401
    assert expired.json() == unknown.json()
    assert expired.json()["code"] == "INVALID_PASSWORD_RESET_TOKEN"
    assert login(api, OLD_PASSWORD).status_code == 200

    assert request_reset(api).status_code == 202
    fresh = token_from_mail(mail)
    assert confirm(api, fresh).status_code == 204
    used = confirm(api, fresh)
    assert used.status_code == 401
    assert used.json() == unknown.json()


def test_failed_delivery_can_be_retried(
    api: TestClient, mail: FakeMailSender, caplog: pytest.LogCaptureFixture
) -> None:
    register(api)
    assert request_reset(api).status_code == 202
    superseded = token_from_mail(mail)
    mail.fail = True
    failed = request_reset(api)
    assert failed.status_code == 202
    assert len(mail.messages) == 1
    assert "Test SMTP failure" in caplog.text
    assert EMAIL not in caplog.text
    assert login(api, OLD_PASSWORD).status_code == 200

    mail.fail = False
    retry = request_reset(api)
    assert retry.status_code == 202
    assert failed.json() == retry.json()
    assert confirm(api, superseded).status_code == 401
    assert confirm(api, token_from_mail(mail)).status_code == 204


def test_failed_transaction_rolls_back_password_change_and_preserves_token(
    api: TestClient, mail: FakeMailSender, monkeypatch: pytest.MonkeyPatch
) -> None:
    register(api)
    assert request_reset(api).status_code == 202
    token = token_from_mail(mail)
    remove = SqlPasswordResetRepository.remove

    def fail_after_removing(self: SqlPasswordResetRepository, user_id: UserId) -> None:
        remove(self, user_id)
        raise RuntimeError("Test transaction failure")

    browser = TestClient(api.app, raise_server_exceptions=False)
    with monkeypatch.context() as patch:
        patch.setattr(SqlPasswordResetRepository, "remove", fail_after_removing)
        assert confirm(browser, token).status_code == 500

    assert login(api, OLD_PASSWORD).status_code == 200
    assert confirm(api, token).status_code == 204


def test_only_one_simultaneous_confirm_can_change_password(
    migrated_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PASSWORD_RESET_BASE_URL", WEB_ORIGIN)
    mail = FakeMailSender()
    container = replace(
        build_container(Settings()),
        session_factory=create_session_factory(migrated_engine),
        mail_sender=mail,
    )
    app = create_app(container)
    email = f"reset-race-{uuid4()}@example.org"
    browser = TestClient(app)
    try:
        register(browser, email)
        assert request_reset(browser, email).status_code == 202
        token = token_from_mail(mail, email)
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        with ThreadPoolExecutor(max_workers=2) as pool, migrated_engine.connect() as locker:
            locker.execute(
                select(PasswordResetTokenRow)
                .where(PasswordResetTokenRow.token_hash == token_hash)
                .with_for_update()
            )
            passwords = ["winning-or-losing-1", "winning-or-losing-2"]
            pending = [
                pool.submit(confirm, TestClient(app), token, password) for password in passwords
            ]
            try:
                wait_for_lock_waiters(migrated_engine, count=2)
            finally:
                locker.rollback()
            responses = [result.result(timeout=10) for result in pending]

        assert sorted(response.status_code for response in responses) == [204, 401]
        for password, response in zip(passwords, responses, strict=True):
            assert login(browser, password, email).status_code == (
                200 if response.status_code == 204 else 401
            )
    finally:
        with migrated_engine.begin() as connection:
            connection.execute(delete(UserRow).where(UserRow.email == email))
