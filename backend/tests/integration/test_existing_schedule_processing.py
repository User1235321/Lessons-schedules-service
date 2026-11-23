import json
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.bootstrap.container import Container
from app.domain.scheduling.job import JobMessage
from app.infrastructure.persistence.job_lock import PostgresJobExecutionLock
from tests.api_calls import created, new_project, sign_in


def upload(api, owner, project, rows):
    return api.post(
        f"/projects/{project}/imports",
        headers=owner,
        data={"import_mode": "SCHEDULE"},
        files={"file": ("расписание.json", json.dumps({"entries": rows}), "application/json")},
    )


def lesson(hour):
    return {
        "week": "ODD",
        "weekday": "MONDAY",
        "start_time": f"{hour:02}:00",
        "end_time": f"{hour + 1:02}:40",
        "participant_label": "Группа без справочника",
        "teachers": [{"display_name": "Исходная подпись"}],
    }


@pytest.fixture
def storage(monkeypatch, container):
    client = Mock()
    monkeypatch.setattr(container, "object_storage", lambda: client)
    return client


def test_partial_import_returns_conflicts_and_preserves_original(api, container, storage):
    owner = sign_in(api)
    project = new_project(api, owner)
    response = upload(api, owner, project, [dict(lesson(9), weekday="SUNDAY"), {"week": "ODD"}])
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["imported_count"] == 1
    assert {issue["row"] for issue in data["errors"]} == {2}
    assert data["validation"]["status"] == "invalid"
    assert [c["code"] for c in data["validation"]["conflicts"]] == ["NON_STUDY_DAY"]
    path = "/schedules/" + data["schedule_ids"][0]
    saved = api.get(path, headers=owner).json()
    assert saved["source"] == "IMPORTED" and saved["job_id"] is None
    assert saved["entries"][0]["teachers"] == [
        {"teacher_id": None, "display_name": "Исходная подпись"}
    ]
    assert api.post(path + "/validate", headers=owner).json() == data["validation"]
    assert (
        api.patch(
            path + "/entries/" + saved["entries"][0]["id"],
            headers=owner,
            json={"weekday": "MONDAY"},
        ).json()["conflicts"]
        == []
    )
    with container.uow() as uow:
        file = uow.files.get(UUID(project), UUID(data["file"]["id"]))
        assert file.schedule_id == UUID(saved["id"])
        assert storage.put.call_args.args[0] == file.object_key


@pytest.mark.parametrize(
    ("suffix", "body", "kind"),
    [
        ("auto-repair", {}, "AUTO_REPAIR"),
        ("reoptimize", {"mode": "FULL"}, "REOPTIMIZE_FULL"),
        ("reoptimize", {"mode": "MIN_CHANGES"}, "REOPTIMIZE_MIN_CHANGES"),
    ],
)
def test_processing_uses_queued_snapshot_and_returns_owned_result(
    api: TestClient,
    container: Container,
    storage,
    monkeypatch,
    migrated_engine: Engine,
    suffix,
    body,
    kind,
):
    state = Mock()
    state.is_cancel_requested.return_value = False
    state.get_progress.return_value = None
    monkeypatch.setattr(container, "job_state", lambda: state)
    owner = sign_in(api)
    outsider = sign_in(api, "other-schedule-user@example.org")
    project = new_project(api, owner)
    base = f"/projects/{project}"
    group = created(api, base + "/groups", owner, {
        "name": "Группа без справочника", "student_count": 12,
    })
    subject = created(api, base + "/subjects", owner, {"name": "Физика"})
    capability = {"subject_id": subject["id"], "lesson_type": "LECTURE"}
    teacher = created(api, base + "/teachers", owner, {
        "full_name": "Преподаватель",
        "capabilities": [capability],
        "availability": [{"week": "ANY", "day": "MONDAY", "start": "09:00", "end": "14:00"}],
    })
    workload = created(api, base + "/workloads", owner, {
        **capability,
        "lesson_format": "REMOTE",
        "group_id": group["id"],
        "occurrences_per_cycle": 2,
        "required_teacher_count": 1,
    })
    first = dict(
        lesson(9),
        workload_id=workload["id"],
        subject_name=subject["name"],
        lesson_type="LECTURE",
        lesson_format="REMOTE",
        teachers=[{"teacher_id": teacher["id"], "display_name": teacher["full_name"]}],
    )
    result = upload(api, owner, project, [first, first]).json()
    path = "/schedules/" + result["schedule_ids"][0]
    initial = api.get(path, headers=owner).json()
    fixed = initial["entries"][0]["id"]
    if suffix == "auto-repair":
        body = {"fixed_entry_ids": [fixed]}
    assert api.post(path + "/" + suffix, json=body).status_code == 401
    assert api.post(path + "/" + suffix, json=body, headers=outsider).status_code == 404
    queued = api.post(path + "/" + suffix, json=body, headers=owner)
    assert queued.status_code == 202, queued.text
    job_id = UUID(queued.json()["job_id"])
    job_url = f"/generation-jobs/{job_id}"
    assert api.get(job_url, headers=owner).json()["job_type"] == kind
    assert api.get(job_url, headers=outsider).status_code == 404
    assert api.get(job_url + "/schedules", headers=outsider).status_code == 404
    with container.uow() as uow:
        job = uow.jobs.get(UUID(project), job_id)
        message = uow.job_outbox.get_pending_for_update()
        assert message == JobMessage(job_id, job.project_id, job.job_type)
    api.patch(path + "/entries/" + fixed, headers=owner, json={"subject_name": "После запуска"})
    worker = container.process_job()
    worker.lock = PostgresJobExecutionLock(migrated_engine)
    assert worker.execute(message)
    assert worker.execute(message)
    assert api.get(job_url, headers=owner).json()["status"] == "COMPLETED"
    (variant,) = api.get(job_url + "/schedules", headers=owner).json()
    assert variant["id"] != initial["id"]
    assert variant["source"] == "GENERATED"
    assert variant["entries"][0]["subject_name"] == "Физика"
    assert all(entry["workload_id"] == workload["id"] for entry in variant["entries"])
    assert len(variant["entries"]) == 2
    assert (
        api.post("/schedules/" + variant["id"] + "/validate", headers=owner).json()["status"]
        == "valid"
    )
    if suffix == "auto-repair":
        assert all(
            variant["entries"][0][k] == first[k]
            for k in ("week", "weekday", "start_time", "end_time")
        )
    assert api.post(path + "/validate", headers=owner).json()["status"] == "invalid"


def test_invalid_requests_do_not_create_jobs_or_access_other_projects(api, storage, container):
    owner = sign_in(api)
    project = new_project(api, owner)
    outsider = sign_in(api, "other-import-user@example.org")
    assert upload(api, outsider, project, [lesson(9)]).status_code == 404
    storage.put.assert_not_called()
    path = "/schedules/" + upload(api, owner, project, [lesson(9)]).json()["schedule_ids"][0]
    for suffix, body in [
        ("auto-repair", {"fixed_entry_ids": [str(uuid4())]}),
        ("reoptimize", {"mode": "unknown"}),
    ]:
        assert api.post(path + "/" + suffix, headers=owner, json=body).status_code == 422
    with container.uow() as uow:
        assert uow.job_outbox.get_pending_for_update() is None


def test_processing_without_workloads_returns_diagnostics(
    api, container, storage, monkeypatch, migrated_engine
):
    state = Mock()
    state.is_cancel_requested.return_value = False
    state.get_progress.return_value = None
    monkeypatch.setattr(container, "job_state", lambda: state)
    owner = sign_in(api)
    project = new_project(api, owner)
    saved = upload(api, owner, project, [lesson(9)]).json()
    path = "/schedules/" + saved["schedule_ids"][0]
    queued = api.post(path + "/reoptimize", headers=owner, json={"mode": "FULL"})
    assert queued.status_code == 202
    with container.uow() as uow:
        message = uow.job_outbox.get_pending_for_update()
    worker = container.process_job()
    worker.lock = PostgresJobExecutionLock(migrated_engine)
    assert worker.execute(message)
    job_url = "/generation-jobs/" + queued.json()["job_id"]
    result = api.get(job_url, headers=owner).json()
    assert result["status"] == "COMPLETED"
    assert result["diagnostics"]
    assert api.get(job_url + "/schedules", headers=owner).json() == []
    assert api.get(path, headers=owner).json()["source"] == "IMPORTED"


def test_text_only_resources_report_overlaps(api, storage):
    owner = sign_in(api)
    project = new_project(api, owner)
    entry = dict(lesson(9), room_name="101", lesson_format="ONSITE")
    data = upload(api, owner, project, [entry, entry]).json()
    assert data["imported_count"] == 2
    assert {item["code"] for item in data["validation"]["conflicts"]} == {
        "GROUP_OVERLAP", "ROOM_OVERLAP", "TEACHER_OVERLAP",
    }
