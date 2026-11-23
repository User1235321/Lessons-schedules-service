from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, time
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import sessionmaker

from app.bootstrap.api import create_app
from app.bootstrap.container import Container
from app.domain.scheduling.job import Job, JobStatus, JobType, ResultMode, ResultOptions
from app.domain.scheduling.schedule import (
    CriterionScore,
    LessonFormat,
    Schedule,
    ScheduleEntry,
    ScheduleSource,
    TeacherAssignment,
)
from app.domain.shared.ids import JobId, ProjectId, ScheduleEntryId, ScheduleId
from app.domain.shared.week import Weekday
from app.infrastructure.persistence.models import ScheduleRow, UserRow
from tests.api_calls import created, new_project, sign_in
from tests.database import wait_for_lock_waiters


def imported_entry(hour: int, **changes) -> ScheduleEntry:
    return replace(
        ScheduleEntry(
            id=ScheduleEntryId(uuid4()),
            week="ODD",
            weekday=Weekday.MONDAY,
            start_time=time(hour),
            end_time=time(hour + 1, 40),
            subject_name="Физика",
            participant_label="Группа 1",
            lesson_type="LECTURE",
        ),
        **changes,
    )


def save_imported(
    container: Container,
    project_id: str,
    *entries: ScheduleEntry,
) -> Schedule:
    schedule = Schedule(
        id=ScheduleId(uuid4()),
        project_id=ProjectId(UUID(project_id)),
        source=ScheduleSource.IMPORTED,
        entries=entries,
        created_at=datetime.now(UTC),
    )
    with container.uow() as uow:
        uow.schedules.add(schedule)
        uow.commit()
    return schedule


def test_patch_persists_conflict_and_validate_clears_after_correction(
    api: TestClient,
    container: Container,
) -> None:
    owner = sign_in(api)
    project_id = new_project(api, owner)
    base = f"/projects/{project_id}"
    subject = created(api, f"{base}/subjects", owner, {"name": "Физика"})
    group = created(api, f"{base}/groups", owner, {"name": "Группа 1", "student_count": 20})
    capability = {"subject_id": subject["id"], "lesson_type": "LECTURE"}
    teacher = created(
        api,
        f"{base}/teachers",
        owner,
        {
            "full_name": "Иванов Иван Иванович",
            "capabilities": [capability],
            "availability": [{"week": "ANY", "day": "MONDAY", "start": "09:00", "end": "18:00"}],
        },
    )
    room = created(
        api,
        f"{base}/rooms",
        owner,
        {
            "name": "Аудитория 1",
            "room_type": "LECTURE",
            "capacity": 30,
            "availability": [
                {"week": "ANY", "weekday": "MONDAY", "start_time": "09:00", "end_time": "18:00"}
            ],
        },
    )
    workload = created(
        api,
        f"{base}/workloads",
        owner,
        {
            **capability,
            "lesson_format": "ONSITE",
            "group_id": group["id"],
            "occurrences_per_cycle": 2,
            "required_teacher_count": 1,
        },
    )
    now = datetime.now(UTC)
    job = Job(
        id=JobId(uuid4()),
        project_id=ProjectId(UUID(project_id)),
        job_type=JobType.GENERATE,
        status=JobStatus.COMPLETED,
        result_options=ResultOptions(ResultMode.TOP_N, 2),
        created_at=now,
        started_at=now,
        finished_at=now,
    )
    first = imported_entry(
        9,
        workload_id=UUID(workload["id"]),
        lesson_format=LessonFormat.ONSITE,
        room_id=UUID(room["id"]),
        room_name=room["name"],
        teachers=(TeacherAssignment(teacher["full_name"], UUID(teacher["id"])),),
    )
    second = replace(first, id=ScheduleEntryId(uuid4()), week="EVEN")
    saved = Schedule(
        id=ScheduleId(uuid4()),
        project_id=job.project_id,
        source=ScheduleSource.GENERATED,
        job_id=job.id,
        result_index=1,
        criterion_scores=(CriterionScore("STUDENT_GAPS", 0),),
        created_at=now,
        entries=(first, second),
    )
    variant = replace(
        saved,
        id=ScheduleId(uuid4()),
        result_index=2,
        entries=tuple(replace(entry, id=ScheduleEntryId(uuid4())) for entry in saved.entries),
    )
    with container.uow() as uow:
        uow.jobs.add(job)
        uow.schedules.add(saved)
        uow.schedules.add(variant)
        uow.commit()

    path = f"/schedules/{saved.id}"
    entry_url = f"{path}/entries/{second.id}"
    response = api.get(path, headers=owner)
    assert response.status_code == 200
    original = response.json()
    assert [entry["week"] for entry in original["entries"]] == ["ODD", "EVEN"]
    assert original["criterion_scores"] == {"STUDENT_GAPS": 0}
    assert api.post(f"{path}/validate", headers=owner).json() == {
        "status": "valid",
        "conflicts": [],
    }

    response = api.patch(entry_url, json={"week": "ODD"}, headers=owner)
    assert response.status_code == 200
    edited = response.json()
    assert edited["entry"]["week"] == "ODD"
    assert {item["code"] for item in edited["conflicts"]} == {
        "GROUP_OVERLAP",
        "ROOM_OVERLAP",
        "TEACHER_OVERLAP",
    }
    for conflict in edited["conflicts"]:
        assert set(conflict["entry_ids"]) == {str(first.id), str(second.id)}
        assert conflict["message"] and conflict["details"]["resource_id"]

    reopened = TestClient(api.app, base_url=str(api.base_url))
    persisted = reopened.get(path, headers=owner).json()
    assert persisted["entries"] == [original["entries"][0], edited["entry"]]
    assert reopened.post(f"{path}/validate", headers=owner).json() == {
        "status": "invalid",
        "conflicts": edited["conflicts"],
    }
    corrected = reopened.patch(
        entry_url, json={"start_time": "11:00", "end_time": "12:40"}, headers=owner
    )
    assert corrected.status_code == 200
    assert corrected.json()["conflicts"] == []
    assert reopened.post(f"{path}/validate", headers=owner).json()["status"] == "valid"

    results = api.get(f"/generation-jobs/{job.id}/schedules", headers=owner)
    assert results.status_code == 200
    first_result, other_result = results.json()
    assert first_result["entries"][1]["start_time"] == "11:00"
    assert other_result == api.get(f"/schedules/{variant.id}", headers=owner).json()
    assert other_result["entries"][1]["week"] == "EVEN"
    assert other_result["entries"][1]["start_time"] == "09:00"

    unlinked = reopened.patch(entry_url, json={"room_id": None}, headers=owner)
    assert unlinked.status_code == 200
    assert unlinked.json()["entry"]["room_id"] is None
    assert unlinked.json()["entry"]["room_name"] == room["name"]
    assert [conflict["code"] for conflict in unlinked.json()["conflicts"]] == ["ROOM_REQUIRED"]

    remote = reopened.patch(entry_url, json={"lesson_format": "REMOTE"}, headers=owner)
    assert remote.status_code == 200
    assert remote.json()["entry"]["room_id"] is None
    assert remote.json()["entry"]["room_name"] is None
    assert reopened.get(path, headers=owner).json()["entries"][0]["lesson_format"] == "ONSITE"
    assert (
        reopened.get(f"{base}/workloads/{workload['id']}", headers=owner).json()["lesson_format"]
        == "ONSITE"
    )

    constraint = created(
        api,
        f"{base}/constraints",
        owner,
        {
            "constraint_type": "MIN_START_TIME",
            "scope": {"type": "GROUP", "id": group["id"]},
            "parameters": {"time": "10:00"},
        },
    )
    assert reopened.post(f"{path}/validate", headers=owner).json()["conflicts"] == [
        {
            "code": "MIN_START_TIME",
            "message": "Занятие начинается раньше разрешённого времени",
            "entry_ids": [str(first.id)],
            "details": {"constraint_id": constraint["id"]},
        },
    ]


def test_imported_schedule_preserves_labels_and_checks_known_resources(
    api: TestClient,
    container: Container,
) -> None:
    owner = sign_in(api)
    project = new_project(api, owner)
    subject = created(api, f"/projects/{project}/subjects", owner, {"name": "Физика"})
    teacher = created(
        api,
        f"/projects/{project}/teachers",
        owner,
        {
            "full_name": "Знакомый преподаватель",
            "capabilities": [{"subject_id": subject["id"], "lesson_type": "LECTURE"}],
            "availability": [{"week": "ANY", "day": "MONDAY", "start": "09:00", "end": "13:00"}],
        },
    )
    known = TeacherAssignment("Исходная подпись", UUID(teacher["id"]))
    first = imported_entry(
        9, lesson_format=LessonFormat.ONSITE, room_name="А-17", teachers=(known,)
    )
    second = imported_entry(
        10, lesson_format=LessonFormat.ONSITE, room_name="А-17", teachers=(known,)
    )
    imported = save_imported(container, project, first, second)
    path = f"/schedules/{imported.id}"
    before = api.get(path, headers=owner).json()
    assert before["job_id"] is None
    assert before["entries"][0]["teachers"][0]["display_name"] == "Исходная подпись"
    assert before["entries"][0]["room_name"] == "А-17"
    conflicts = api.post(f"{path}/validate", headers=owner).json()["conflicts"]
    assert [item["code"] for item in conflicts] == [
        "GROUP_OVERLAP", "ROOM_OVERLAP", "TEACHER_OVERLAP",
    ]

    entry_url = f"{path}/entries/{first.id}"
    for invalid in (
        {"start_time": "12:00"},
        {"end_time": None},
        {"start_time": "09:00:00"},
        {"lesson_format": "REMOTE", "room_name": "А-17"},
        {"teachers": None},
    ):
        assert api.patch(entry_url, json=invalid, headers=owner).status_code == 422
        assert api.get(path, headers=owner).json() == before

    response = api.patch(
        entry_url,
        json={
            "lesson_format": "REMOTE",
            "subject_name": None,
            "teachers": [{"display_name": "Имя из файла"}],
        },
        headers=owner,
    )
    assert response.status_code == 200
    entry = response.json()["entry"]
    assert entry["subject_name"] is None
    assert entry["participant_label"] == first.participant_label
    assert entry["room_id"] is None and entry["room_name"] is None
    assert entry["teachers"] == [{"display_name": "Имя из файла", "teacher_id": None}]
    validation = api.post(f"{path}/validate", headers=owner).json()
    assert validation["status"] == "invalid"
    assert [item["code"] for item in validation["conflicts"]] == ["GROUP_OVERLAP"]

    replacement = api.patch(
        entry_url,
        json={
            "teachers": [{"teacher_id": teacher["id"], "display_name": "Подмена подписи"}],
        },
        headers=owner,
    )
    assert replacement.status_code == 200
    assert replacement.json()["entry"]["teachers"] == [
        {"teacher_id": teacher["id"], "display_name": teacher["full_name"]},
    ]
    assert [item["code"] for item in replacement.json()["conflicts"]] == [
        "GROUP_OVERLAP", "TEACHER_OVERLAP",
    ]
    corrected = api.patch(
        f"{path}/entries/{second.id}",
        json={"start_time": "11:00", "end_time": "12:40"},
        headers=owner,
    )
    assert corrected.status_code == 200
    assert corrected.json()["conflicts"] == []
    assert api.post(f"{path}/validate", headers=owner).json()["status"] == "valid"


def test_schedule_routes_enforce_ownership_entry_scope_and_resource_scope(
    api: TestClient,
    container: Container,
) -> None:
    owner = sign_in(api)
    other_user = sign_in(api, "other@example.org")
    project = new_project(api, owner)
    other_project = new_project(api, other_user)
    first, other = imported_entry(9), imported_entry(11)
    saved = save_imported(container, project, first)
    save_imported(container, project, other)
    path = f"/schedules/{saved.id}"
    missing = f"/schedules/{uuid4()}"
    for method, suffix, request_kwargs in (
        ("GET", "", {}),
        ("POST", "/validate", {}),
        ("PATCH", f"/entries/{first.id}", {"json": {"week": "EVEN"}}),
    ):
        assert api.request(method, path + suffix, **request_kwargs).status_code == 401
        denied = api.request(method, path + suffix, headers=other_user, **request_kwargs)
        absent = api.request(method, missing + suffix, headers=other_user, **request_kwargs)
        assert denied.status_code == absent.status_code == 404
        assert denied.json()["code"] == absent.json()["code"]
        assert denied.json()["message"] == absent.json()["message"]

    assert api.patch(f"{path}/entries/{other.id}", json={}, headers=owner).status_code == 404
    room = created(
        api,
        f"/projects/{other_project}/rooms",
        other_user,
        {
            "name": "Чужая аудитория",
            "room_type": "LECTURE",
            "capacity": 30,
            "availability": [
                {"week": "ANY", "weekday": "MONDAY", "start_time": "09:00", "end_time": "18:00"}
            ],
        },
    )
    result = api.patch(f"{path}/entries/{first.id}", json={"room_id": room["id"]}, headers=owner)
    assert result.status_code == 422
    assert result.json()["details"] == {"field": "room_id"}
    assert api.get(path, headers=owner).json()["entries"][0]["room_id"] is None


def test_concurrent_patches_keep_both_edits(
    migrated_engine: Engine,
    container: Container,
) -> None:
    live = replace(
        container,
        session_factory=sessionmaker(bind=migrated_engine, expire_on_commit=False),
    )
    app = create_app(live)
    api = TestClient(app, base_url="https://testserver")
    email = f"schedule-race-{uuid4()}@example.org"
    owner = sign_in(api, email)
    try:
        project_id = new_project(api, owner)
        first, second = imported_entry(9), imported_entry(11)
        schedule = save_imported(live, project_id, first, second)
        url = f"/schedules/{schedule.id}"
        with ThreadPoolExecutor(max_workers=2) as pool, migrated_engine.connect() as locker:
            locker.execute(
                select(ScheduleRow.id).where(ScheduleRow.id == schedule.id).with_for_update()
            )
            futures = [
                pool.submit(
                    TestClient(app, base_url="https://testserver").patch,
                    f"{url}/entries/{entry.id}",
                    json={"participant_label": label},
                    headers=owner,
                )
                for entry, label in ((first, "Новая группа 1"), (second, "Новая группа 2"))
            ]
            try:
                wait_for_lock_waiters(migrated_engine, 2)
            finally:
                locker.rollback()
            assert [future.result(timeout=10).status_code for future in futures] == [200, 200]
        response = api.get(url, headers=owner)
        assert [entry["participant_label"] for entry in response.json()["entries"]] == [
            "Новая группа 1",
            "Новая группа 2",
        ]
    finally:
        with migrated_engine.begin() as connection:
            connection.execute(delete(UserRow).where(UserRow.email == email))
