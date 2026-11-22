from uuid import UUID

from app.infrastructure.persistence.job_lock import PostgresJobExecutionLock
from tests.api_calls import created, new_project, sign_in


def test_worker_uses_queued_project_data_and_persists_scores_and_diagnostics(
    api,
    container,
    migrated_engine,
    redis_client,
):
    client = api
    auth = sign_in(client)
    base = f"/projects/{new_project(client, auth)}"
    container.redis = redis_client
    group = created(client, base + "/groups", auth, {"name": "Группа 1", "student_count": 12})
    subject = created(client, base + "/subjects", auth, {"name": "Физика"})
    capability = {"subject_id": subject["id"], "lesson_type": "LECTURE"}
    workload = created(
        client,
        base + "/workloads",
        auth,
        {
            **capability,
            "lesson_format": "REMOTE",
            "group_id": group["id"],
            "occurrences_per_cycle": 1,
            "required_teacher_count": 1,
        },
    )
    criteria = [{"criterion_type": "TEACHER_PREFERENCES", "is_active": True, "priority": 1}]
    assert (
        client.put(
            base + "/optimization-criteria", headers=auth, json={"criteria": criteria}
        ).status_code
        == 200
    )

    def queue():
        response = client.post(base + "/generation-jobs", headers=auth, json={})
        assert response.status_code == 202
        return response.json()["job_id"]

    no_teacher = queue()
    teacher = created(
        client,
        base + "/teachers",
        auth,
        {
            "full_name": "Иванов",
            "capabilities": [capability],
            "availability": [{"week": "ANY", "day": "MONDAY", "start": "09:00", "end": "14:00"}],
            "preferences": [{"week": "ODD", "day": "MONDAY", "start": "12:00", "end": "13:40"}],
        },
    )
    with_teacher = queue()
    assert (
        client.put(base + "/optimization-criteria", headers=auth, json={"criteria": []}).status_code
        == 200
    )
    assert (
        client.patch(
            base + "/teachers/" + teacher["id"], headers=auth, json={"full_name": "После запуска"}
        ).status_code
        == 200
    )

    for job_id in (no_teacher, with_teacher):
        with container.uow() as uow:
            message = uow.job_outbox.get_pending_for_update()
            assert message.job_id == UUID(job_id)
            uow.job_outbox.mark_published(message.job_id, container.clock.now())
            uow.commit()
        process = container.process_job()
        process.lock = PostgresJobExecutionLock(migrated_engine)
        assert process.execute(message)
        assert process.execute(message)
    missing_url = "/generation-jobs/" + no_teacher
    result = client.get(missing_url, headers=auth).json()
    assert result["status"] == "COMPLETED"
    assert result["diagnostics"][0]["workload_ids"] == [workload["id"]]
    assert client.get(missing_url + "/schedules", headers=auth).json() == []
    (variant,) = client.get(f"/generation-jobs/{with_teacher}/schedules", headers=auth).json()
    assert variant["criterion_scores"] == {"TEACHER_PREFERENCES": 0}
    (entry,) = variant["entries"]
    assert entry["start_time"] == "12:00" and entry["week"] == "ODD"
    assert entry["teachers"] == [{"teacher_id": teacher["id"], "display_name": "Иванов"}]


def test_oversized_project_never_enters_queue(api, container):
    owner = sign_in(api)
    project = new_project(api, owner)
    base = f"/projects/{project}"
    created(api, base + "/groups", owner, {"name": "Поток", "student_count": 52647})
    result = api.post(base + "/generation-jobs", headers=owner, json={})
    assert result.status_code == 409
    assert result.json()["details"] == {"field": "students", "actual": 52647, "limit": 52646}
    with container.uow() as uow:
        assert uow.job_outbox.get_pending_for_update() is None
