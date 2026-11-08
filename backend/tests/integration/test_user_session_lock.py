import time
from collections.abc import Iterator
from dataclasses import replace
from threading import Thread
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import Engine, delete, select, text

from app.api.cookies import REFRESH_COOKIE_NAME
from app.bootstrap.api import create_app
from app.bootstrap.container import Container, build_container
from app.bootstrap.settings import Settings
from app.infrastructure.persistence.database import create_session_factory
from app.infrastructure.persistence.models import UserRow, UserSessionRow

BASE_URL = "https://testserver"


@pytest.fixture
def email(migrated_engine: Engine) -> Iterator[str]:
    """Адрес пользователя, которого тест создаёт настоящими коммитами.

    После теста пользователь удаляется вместе с сессиями, чтобы не мешать другим тестам.
    """
    address = f"race-{uuid4()}@mail.ru"
    yield address
    with migrated_engine.begin() as connection:
        connection.execute(delete(UserRow).where(UserRow.email == address))


@pytest.fixture
def live_container(migrated_engine: Engine) -> Container:
    # Общая откатываемая транзакция из conftest не подходит: запросам нужны свои соединения
    # и транзакции, чтобы ждать друг друга на блокировке строки
    return replace(
        build_container(Settings()), session_factory=create_session_factory(migrated_engine)
    )


def browser(app: FastAPI, refresh_token: str) -> TestClient:
    client = TestClient(app, base_url=BASE_URL)
    # Домен и путь как у cookie, который ставит сервер
    client.cookies.set(REFRESH_COOKIE_NAME, refresh_token, domain="testserver.local", path="/auth")
    return client


def refresh_in_background(client: TestClient, responses: list[Response]) -> Thread:
    thread = Thread(target=lambda: responses.append(client.post("/auth/refresh")))
    thread.start()
    return thread


def wait_for_lock_waiters(engine: Engine, count: int, timeout: float = 10) -> None:
    query = text(
        "SELECT count(*) FROM pg_stat_activity"
        " WHERE wait_event_type = 'Lock' AND datname = current_database()"
    )
    deadline = time.monotonic() + timeout
    with engine.connect() as connection:
        while time.monotonic() < deadline:
            waiting = connection.scalar(query)
            # pg_stat_activity запоминается до конца транзакции, свежие данные — в новой
            connection.rollback()
            if waiting == count:
                return
            time.sleep(0.02)
    raise AssertionError(f"Не дождались {count} запросов, ждущих блокировку")


def test_only_one_of_two_simultaneous_refreshes_wins(
    migrated_engine: Engine, live_container: Container, email: str
) -> None:
    app = create_app(live_container)
    signup = TestClient(app, base_url=BASE_URL)
    signup.post("/auth/register", json={"email": email, "password": "secret1"})
    token = signup.cookies[REFRESH_COOKIE_NAME]
    token_hash = live_container.tokens.hash_refresh_token(token)
    responses: list[Response] = []

    with migrated_engine.connect() as locker:
        # Тест сам держит строку сессии, и оба refresh встают в очередь на её блокировку.
        # Так они гарантированно идут одновременно, а не один после другого
        locker.execute(
            select(UserSessionRow.id)
            .where(UserSessionRow.refresh_token_hash == token_hash)
            .with_for_update()
        )
        threads = [refresh_in_background(browser(app, token), responses) for _ in range(2)]
        try:
            wait_for_lock_waiters(migrated_engine, count=2)
        finally:
            locker.rollback()
            for thread in threads:
                thread.join(timeout=10)

    assert sorted(response.status_code for response in responses) == [200, 401]
    winner, loser = sorted(responses, key=lambda response: response.status_code)
    assert loser.json()["code"] == "INVALID_REFRESH_TOKEN"
    with migrated_engine.connect() as connection:
        stored_hashes = connection.scalars(
            select(UserSessionRow.refresh_token_hash)
            .join(UserRow, UserRow.id == UserSessionRow.user_id)
            .where(UserRow.email == email)
        ).all()
    new_token = winner.cookies[REFRESH_COOKIE_NAME]
    assert stored_hashes == [live_container.tokens.hash_refresh_token(new_token)]
