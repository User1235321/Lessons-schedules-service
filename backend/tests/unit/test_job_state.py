from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from redis.exceptions import ConnectionError

from app.application.scheduling.ports import JobStateStoreError
from app.domain.scheduling.job import JobProgress
from app.domain.shared.ids import JobId
from app.infrastructure.job_state import RedisJobStateStore


def test_missing_state_is_distinct_from_failed_read() -> None:
    client = MagicMock()
    client.get.return_value = None
    client.exists.return_value = 0
    store = RedisJobStateStore(client)
    job_id = JobId(uuid4())

    assert store.get_progress(job_id) is None
    assert not store.is_cancel_requested(job_id)
    client.get.side_effect = ConnectionError("offline")
    with pytest.raises(JobStateStoreError):
        store.get_progress(job_id)


def test_progress_and_cancellation_use_independent_keys() -> None:
    client = MagicMock()
    values = {}
    client.set.side_effect = lambda key, value: values.update({key: value})
    client.get.side_effect = values.get
    client.exists.side_effect = lambda key: key in values
    store = RedisJobStateStore(client)
    job_id = JobId(uuid4())

    store.request_cancel(job_id)
    store.set_progress(job_id, JobProgress(42))
    store.request_cancel(job_id)

    assert store.get_progress(job_id) == JobProgress(42)
    assert store.is_cancel_requested(job_id)
    store.clear(job_id)
    client.delete.assert_called_once_with(
        f"schedule-job:{job_id}:progress", f"schedule-job:{job_id}:cancel"
    )


@pytest.mark.parametrize("value", ["broken", "NaN", "101", "-1"])
def test_corrupt_progress_is_not_reported_as_missing(value: str) -> None:
    client = MagicMock()
    client.get.return_value = value
    with pytest.raises(JobStateStoreError):
        RedisJobStateStore(client).get_progress(JobId(uuid4()))


def test_failed_completion_is_reported_as_state_store_error() -> None:
    client = MagicMock()
    client.pipeline.side_effect = ConnectionError("offline")
    with pytest.raises(JobStateStoreError):
        RedisJobStateStore(client).complete(JobId(uuid4()), datetime(2026, 11, 13, tzinfo=UTC))
