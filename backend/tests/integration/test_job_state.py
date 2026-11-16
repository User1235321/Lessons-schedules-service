from datetime import UTC, datetime, timedelta
from uuid import uuid4

from redis import Redis

from app.domain.scheduling.job import JobProgress
from app.domain.shared.ids import JobId
from app.infrastructure.job_state import RedisJobStateStore


def test_final_progress_has_fixed_expiry_and_removes_cancel(redis_client: Redis) -> None:
    store = RedisJobStateStore(redis_client)
    job_id = JobId(uuid4())
    expires_at = datetime.now(UTC) + timedelta(hours=24)
    store.set_progress(job_id, JobProgress(42))
    store.request_cancel(job_id)
    store.complete(job_id, expires_at)

    assert store.get_progress(job_id) == JobProgress(100)
    assert not store.is_cancel_requested(job_id)
    key = f"schedule-job:{job_id}:progress"
    assert redis_client.pexpiretime(key) == int(expires_at.timestamp() * 1000)

    store.request_cancel(job_id)
    store.complete(job_id, expires_at)
    assert redis_client.pexpiretime(key) == int(expires_at.timestamp() * 1000)
    assert not store.is_cancel_requested(job_id)


def test_completion_does_not_restore_expired_progress(redis_client: Redis) -> None:
    store = RedisJobStateStore(redis_client)
    job_id = JobId(uuid4())
    store.set_progress(job_id, JobProgress(42))
    store.request_cancel(job_id)

    store.complete(job_id, datetime.now(UTC) - timedelta(seconds=1))

    assert store.get_progress(job_id) is None
    assert not store.is_cancel_requested(job_id)
