import json
from dataclasses import replace
from urllib.parse import quote
from uuid import UUID, uuid4

import pytest

from app.domain.scheduling.job import Job, JobStatus, JobType, ResultMode, ResultOptions
from app.domain.scheduling.schedule import CriterionScore, ScheduleSource
from tests.api_calls import created, new_project, sign_in


@pytest.fixture
def objects(container, monkeypatch):
    class MemoryObjects(dict):
        def put(self, key, data, *, content_type):
            self[key] = data

        def delete(self, key):
            self.pop(key, None)

    storage = MemoryObjects()
    monkeypatch.setattr(container, "object_storage", lambda: storage)
    return storage


def upload(api, owner, project, mode, name, content, **fields):
    return api.post(
        f"/projects/{project}/imports",
        headers=owner,
        data={"import_mode": mode, **fields},
        files={"file": (name, content)},
    )


def export(api, owner, project, **body):
    result = api.post(f"/projects/{project}/exports", headers=owner, json=body)
    assert result.status_code == 201, result.text
    file = result.json()
    assert file["category"] == "EXPORT" and file["project_id"] == project
    response = api.get("/files/" + file["id"], headers=owner)
    assert response.status_code == 200
    assert response.headers["content-disposition"].endswith(quote(file["original_name"]))
    assert len(response.content) == file["size_bytes"]
    return file, response.content


@pytest.mark.parametrize("extension", ["xlsx", "ods", "csv", "json"])
def test_schedule_formats_preserve_text_and_teachers_and_check_file_ownership(
    api, objects, extension
):
    owner, other = sign_in(api), sign_in(api, "outsider@example.org")
    project = new_project(api, owner)
    entry = {
        "week": "ODD",
        "weekday": "MONDAY",
        "start_time": "09:00",
        "end_time": "10:40",
        "subject_name": "=Физика, часть 2",
        "participant_label": "Группа «Ёж»",
        "teachers": [{"display_name": "Иванов"}, {"display_name": "Петрова"}],
    }
    original = json.dumps([entry], ensure_ascii=False).encode()
    saved = upload(api, owner, project, "SCHEDULE", "русский.json", original).json()
    schedule = saved["schedule_ids"][0]
    file, content = export(
        api, owner, project, scope="SCHEDULE", file_format=extension, schedule_id=schedule
    )
    if extension == "csv":
        assert "'=Физика, часть 2" in content.decode("utf-8-sig")
    listing = f"/projects/{project}/files"
    assert api.get(listing, headers=other).status_code == 404
    assert api.get(listing, headers=owner, params={"category": "UPLOAD"}).json() == [saved["file"]]
    assert api.get(listing, headers=owner, params={"category": "EXPORT"}).json() == [file]
    path = "/files/" + file["id"]
    assert api.get(path).status_code == 401
    assert api.get(path, headers=other).status_code == 404
    assert api.delete(path, headers=other).status_code == 404
    assert api.get(path, headers=owner).content == content
    again = upload(api, owner, project, "SCHEDULE", "повтор." + extension, content).json()
    assert again["errors"] == [] and again["imported_count"] == 1
    restored = api.get("/schedules/" + again["schedule_ids"][0], headers=owner).json()["entries"][0]
    assert (
        restored["subject_name"] == entry["subject_name"]
        and restored["participant_label"] == entry["participant_label"]
    )
    assert [t["display_name"] for t in restored["teachers"]] == ["Иванов", "Петрова"]
    assert api.delete(path, headers=owner).status_code == 204
    assert api.get(path, headers=owner).status_code == 404
    assert not any(file["id"] in key for key in objects)
    assert api.get("/schedules/" + schedule, headers=owner).status_code == 200
    another = new_project(api, owner, "Другой проект")
    assert (
        api.post(
            f"/projects/{another}/exports",
            headers=owner,
            json={"scope": "SCHEDULE", "schedule_id": schedule, "file_format": extension},
        ).status_code
        == 404
    )


def test_selected_fields_partial_rows_and_update_scope(api, objects):
    owner, other = sign_in(api), sign_in(api, "other@example.org")
    project = new_project(api, owner)
    outsider = new_project(api, other)
    foreign = created(
        api, f"/projects/{outsider}/groups", other, {"name": "Чужая", "student_count": 4}
    )
    path = f"/projects/{project}/groups"
    group = created(api, path, owner, {"name": "Первая", "student_count": 12})
    content = (
        "id;Название;Размер;Лишнее\n"
        f"{group['id']};Новая;;ничего\n"
        ";Вторая;5;пропустить\n;Брак;-1;пропустить\n"
        f"{foreign['id']};Чужая правка;;пропустить\n"
        ";Вторая;5;дубликат\n;Последняя;3;после ошибки БД\n"
    ).encode()
    data = upload(
        api,
        owner,
        project,
        "RESOURCE",
        "группы.csv",
        content,
        resource="groups",
        mapping=json.dumps({"Название": "name", "Размер": "student_count"}),
    ).json()
    assert data["imported_count"] == 3, data
    assert {issue["row"] for issue in data["errors"]} == {4, 5, 6}
    groups = {x["name"]: x["student_count"] for x in api.get(path, headers=owner).json()}
    assert groups == {"Новая": 12, "Вторая": 5, "Последняя": 3}
    assert api.get("/files/" + data["file"]["id"], headers=owner).content == content
    assert api.get(f"/projects/{outsider}/groups", headers=other).json()[0]["name"] == "Чужая"


def test_project_archive_restores_new_ids_references_settings_and_scores(api, container, objects):
    owner = sign_in(api)
    source = new_project(api, owner, "Осень — физика")
    base = "/projects/" + source
    subject = created(api, base + "/subjects", owner, {"name": "Физика"})
    group = created(api, base + "/groups", owner, {"name": "Группа", "student_count": 12})
    subgroup = created(
        api,
        base + "/subgroups",
        owner,
        {"name": "Подгруппа", "student_count": 6, "group_id": group["id"]},
    )
    created(api, base + "/streams", owner, {"name": "Поток", "group_ids": [group["id"]]})
    cap = {"subject_id": subject["id"], "lesson_type": "LECTURE"}
    teacher = created(
        api,
        base + "/teachers",
        owner,
        {
            "full_name": "Петрова",
            "capabilities": [cap],
            "availability": [{"week": "ANY", "day": "MONDAY", "start": "09:00", "end": "15:00"}],
        },
    )
    room = created(
        api,
        base + "/rooms",
        owner,
        {
            "name": "Аудитория",
            "capacity": 30,
            "room_type": "PRACTICE_SPECIALIZED",
            "availability": [
                {"week": "ANY", "weekday": "MONDAY", "start_time": "09:00", "end_time": "15:00"}
            ],
            "capabilities": [cap],
        },
    )
    work = created(
        api,
        base + "/workloads",
        owner,
        {
            **cap,
            "subgroup_id": subgroup["id"],
            "lesson_format": "ONSITE",
            "occurrences_per_cycle": 1,
            "required_teacher_count": 1,
        },
    )
    created(
        api,
        base + "/constraints",
        owner,
        {
            "constraint_type": "MIN_START_TIME",
            "scope": {"type": "GROUP", "id": group["id"]},
            "parameters": {"time": "09:00"},
        },
    )
    criteria = [{"criterion_type": "STUDENT_GAPS", "is_active": True, "priority": 1}]
    assert (
        api.put(
            base + "/optimization-criteria", headers=owner, json={"criteria": criteria}
        ).status_code
        == 200
    )
    entry = {
        "week": "ODD",
        "weekday": "MONDAY",
        "start_time": "10:00",
        "end_time": "11:40",
        "lesson_format": "ONSITE",
        "workload_id": work["id"],
        "room_id": room["id"],
        "subject_name": "Физика",
        "teachers": [{"teacher_id": teacher["id"], "display_name": "Петрова"}],
    }
    saved = upload(
        api, owner, source, "SCHEDULE", "занятия.json", json.dumps([entry]).encode()
    ).json()
    sid = saved["schedule_ids"][0]
    with container.uow() as uow:
        schedule = uow.schedules.get(UUID(source), UUID(sid))
        job_id = uuid4()
        uow.jobs.add(
            Job(
                id=job_id,
                project_id=UUID(source),
                job_type=JobType.GENERATE,
                status=JobStatus.COMPLETED,
                result_options=ResultOptions(ResultMode.TOP_N, 2),
                created_at=schedule.created_at,
                started_at=schedule.created_at,
                finished_at=schedule.created_at,
            )
        )
        uow.schedules.add(
            replace(
                schedule,
                job_id=job_id,
                source=ScheduleSource.GENERATED,
                id=uuid4(),
                entries=tuple(replace(e, id=uuid4()) for e in schedule.entries),
                result_index=2,
                criterion_scores=(CriterionScore("STUDENT_GAPS", 12.5),),
            )
        )
        uow.commit()
    _, content = export(api, owner, source, scope="PROJECT", file_format="json")
    target = new_project(api, owner, "Пустой")
    dst = "/projects/" + target
    restored = upload(api, owner, target, "PROJECT", "архив.json", content).json()
    assert restored["errors"] == [], restored
    assert len(restored["schedule_ids"]) == 2 and sid not in restored["schedule_ids"]
    assert api.get(dst, headers=owner).json()["name"] == "Осень — физика"
    _, roundtrip = export(api, owner, target, scope="PROJECT", file_format="json")
    a, b = json.loads(content), json.loads(roundtrip)
    ids = {}
    for kind in (
        "subjects",
        "groups",
        "subgroups",
        "teachers",
        "rooms",
        "streams",
        "workloads",
        "constraints",
    ):
        ids[a[kind][0]["id"]] = b[kind][0]["id"]
    assert all(old != new for old, new in ids.items())
    text = json.dumps(a, ensure_ascii=False)
    for old, new in ids.items():
        text = text.replace(old, new)
    expected = json.loads(text)
    for doc in (expected, b):
        doc["schedules"].sort(key=lambda s: s["result_index"] or 0)
    assert expected == b
    assert any(s["criterion_scores"] == {"STUDENT_GAPS": 12.5} for s in b["schedules"])
    refused = upload(api, owner, target, "PROJECT", "архив.json", content).json()
    assert refused["errors"] and refused["imported_count"] == 0
    assert len(api.get(dst + "/groups", headers=owner).json()) == 1
    # Ошибка возникает уже после создания групп, при записи следующего справочника.
    bad = json.loads(content)
    bad["subgroups"][0]["student_count"] = 25
    empty = new_project(api, owner, "Пустой после ошибки")
    failed = upload(api, owner, empty, "PROJECT", "ошибка.json", json.dumps(bad)).json()
    assert failed["imported_count"] == 0 and failed["errors"], failed
    assert api.get(f"/projects/{empty}/subjects", headers=owner).json() == []
    assert api.get(f"/projects/{empty}", headers=owner).json()["name"] == "Пустой после ошибки"
    assert api.get("/files/" + failed["file"]["id"], headers=owner).status_code == 200


@pytest.mark.parametrize("extension", ["xlsx", "ods", "csv", "json"])
def test_resource_mapping_across_file_formats(api, objects, extension):
    owner = sign_in(api)
    project = new_project(api, owner)
    label = "Прикладная математика"
    if extension == "json":
        content = json.dumps({"rows": [{"дисциплина": label, "лишнее": "игнор"}]}).encode()
        column = "дисциплина"
    else:
        entry = {
            "week": "ODD",
            "weekday": "MONDAY",
            "start_time": "09:00",
            "end_time": "10:40",
            "subject_name": label,
        }
        saved = upload(api, owner, project, "SCHEDULE", "занятия.json", json.dumps([entry])).json()
        _, content = export(
            api,
            owner,
            project,
            scope="SCHEDULE",
            file_format=extension,
            schedule_id=saved["schedule_ids"][0],
        )
        column = "subject_name"
    data = upload(
        api,
        owner,
        project,
        "RESOURCE",
        "данные." + extension,
        content,
        resource="subjects",
        mapping=json.dumps({column: "name"}),
    ).json()
    assert data["errors"] == [] and data["imported_count"] == 1
    assert api.get(f"/projects/{project}/subjects", headers=owner).json()[0]["name"] == label


def test_invalid_archive_is_retained_and_foreign_project_is_hidden(api, objects):
    owner, other = sign_in(api), sign_in(api, "another-owner@example.org")
    project = new_project(api, owner)
    body = {"scope": "PROJECT", "file_format": "json"}
    path = f"/projects/{project}/exports"
    assert api.post(path, headers=other, json=body).status_code == 404
    assert api.post(path, headers=owner, json=dict(body, file_format="csv")).status_code == 415
    assert (
        api.post(path, headers=owner, json=dict(body, schedule_id=str(uuid4()))).status_code == 422
    )
    _, content = export(api, owner, project, **body)
    corrupted = json.loads(content)
    corrupted["version"] = 1000
    data = upload(api, owner, project, "PROJECT", "версия.json", json.dumps(corrupted)).json()
    assert data["imported_count"] == 0 and data["errors"][0]["field"] == "version"
    assert api.get("/files/" + data["file"]["id"], headers=owner).status_code == 200
    assert upload(api, other, project, "PROJECT", "архив.json", content).status_code == 404


def test_commit_failure_preserves_file_and_does_not_leak_export(
    api, container, objects, monkeypatch
):
    from app.infrastructure.persistence.uow import SqlUnitOfWork

    owner = sign_in(api)
    project = new_project(api, owner)
    file, original = export(api, owner, project, scope="PROJECT", file_format="json")
    before = dict(objects)

    def fail_commit(self):
        raise RuntimeError("test-commit-error")

    with monkeypatch.context() as change:
        change.setattr(SqlUnitOfWork, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="test-commit-error"):
            api.delete("/files/" + file["id"], headers=owner)
        with pytest.raises(RuntimeError, match="test-commit-error"):
            api.post(
                f"/projects/{project}/exports",
                headers=owner,
                json={"scope": "PROJECT", "file_format": "json"},
            )
    assert dict(objects) == before
    assert api.get("/files/" + file["id"], headers=owner).content == original
    assert api.get(f"/projects/{project}/files", headers=owner).json() == [file]
