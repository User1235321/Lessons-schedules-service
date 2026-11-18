import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, select, text, update

from app.bootstrap.api import create_app
from app.bootstrap.container import build_container
from app.bootstrap.settings import Settings
from app.infrastructure.persistence.database import create_session_factory
from app.infrastructure.persistence.models import (
    Base,
    ProjectRow,
    StreamRow,
    StudentGroupRow,
    UserRow,
    WorkloadRow,
)
from tests.api_calls import created, new_project, sign_in


@pytest.fixture
def live_api(migrated_engine: Engine) -> Iterator[tuple[TestClient, str]]:
    container = replace(
        build_container(Settings()),
        session_factory=create_session_factory(migrated_engine),
    )
    email = f"resource-lock-{uuid4()}@example.org"
    with TestClient(create_app(container)) as api:
        try:
            yield api, email
        finally:
            with migrated_engine.begin() as connection:
                connection.execute(delete(UserRow).where(UserRow.email == email))


def prepare_resource(
    api: TestClient, user: dict[str, str], project: str, resource: str
) -> tuple[str, type[Base], UUID, UUID]:
    group = created(
        api, f"/projects/{project}/groups", user,
        {"name": "301", "student_count": 20},
    )
    group_id = UUID(group["id"])
    if resource == "GROUP":
        return "groups", StudentGroupRow, group_id, group_id
    if resource == "SUBGROUP":
        subgroup = created(
            api, f"/projects/{project}/subgroups", user,
            {"group_id": group["id"], "name": "301-1", "student_count": 10},
        )
        return "subgroups", StudentGroupRow, group_id, UUID(subgroup["id"])
    if resource == "STREAM":
        stream = created(
            api, f"/projects/{project}/streams", user,
            {"name": "Поток", "group_ids": [group["id"]]},
        )
        stream_id = UUID(stream["id"])
        return "streams", StreamRow, stream_id, stream_id

    subject = created(
        api, f"/projects/{project}/subjects", user, {"name": "Математика"}
    )
    workload = created(
        api, f"/projects/{project}/workloads", user,
        {
            "subject_id": subject["id"],
            "group_id": group["id"],
            "lesson_type": "LECTURE",
            "lesson_format": "ONSITE",
            "occurrences_per_cycle": 2,
            "required_teacher_count": 1,
        },
    )
    workload_id = UUID(workload["id"])
    return "workloads", WorkloadRow, workload_id, workload_id


def wait_for_lock_waiter(engine: Engine, timeout: float = 10) -> None:
    query = text(
        "SELECT count(*) FROM pg_stat_activity "
        "WHERE wait_event_type = 'Lock' AND datname = current_database()"
    )
    deadline = time.monotonic() + timeout
    with engine.connect() as observer:
        while time.monotonic() < deadline:
            if observer.scalar(query) >= 1:
                observer.rollback()
                return
            observer.rollback()
            time.sleep(0.02)
    raise AssertionError("Удаление не перешло в ожидание блокировки ресурса")


@pytest.mark.parametrize("resource", ["GROUP", "SUBGROUP", "STREAM", "WORKLOAD"])
def test_deletion_waits_for_resource_without_locking_project(
    migrated_engine: Engine, live_api: tuple[TestClient, str], resource: str
) -> None:
    api, email = live_api
    user = sign_in(api, email)
    project = new_project(api, user)
    path, row_type, lock_id, delete_id = prepare_resource(api, user, project, resource)

    with migrated_engine.connect() as locker:
        locked_id = locker.scalar(
            select(row_type.id).where(row_type.id == lock_id).with_for_update()
        )
        assert locked_id == lock_id
        with ThreadPoolExecutor(max_workers=1) as workers:
            deletion = workers.submit(
                api.delete, f"/projects/{project}/{path}/{delete_id}", headers=user
            )
            try:
                wait_for_lock_waiter(migrated_engine)
                locker.execute(text("SET LOCAL lock_timeout = '2s'"))
                locker.execute(
                    update(ProjectRow)
                    .where(ProjectRow.id == UUID(project))
                    .values(updated_at=datetime.now(UTC))
                )
            finally:
                locker.rollback()
            assert deletion.result(timeout=10).status_code == 204
