from redis import Redis
from redis.exceptions import RedisError

from app.application.scheduling.ports import JobStateStoreError
from app.domain.scheduling.job import JobProgress
from app.domain.shared.errors import InvalidValue
from app.domain.shared.ids import JobId


class RedisJobStateStore:
    def __init__(self, client: Redis) -> None:
        self._client = client

    def get_progress(self, job_id: JobId) -> JobProgress | None:
        try:
            value = self._client.get(self._key(job_id, "progress"))
            return JobProgress(float(value)) if value is not None else None
        except (RedisError, ValueError, InvalidValue) as error:
            raise JobStateStoreError("Не удалось прочитать прогресс задания") from error

    def set_progress(self, job_id: JobId, progress: JobProgress) -> None:
        try:
            self._client.set(self._key(job_id, "progress"), str(progress.percent))
        except RedisError as error:
            raise JobStateStoreError("Не удалось сохранить прогресс задания") from error

    def request_cancel(self, job_id: JobId) -> None:
        try:
            self._client.set(self._key(job_id, "cancel"), "1")
        except RedisError as error:
            raise JobStateStoreError("Не удалось запросить отмену задания") from error

    def is_cancel_requested(self, job_id: JobId) -> bool:
        try:
            return bool(self._client.exists(self._key(job_id, "cancel")))
        except RedisError as error:
            raise JobStateStoreError("Не удалось прочитать запрос отмены задания") from error

    def clear(self, job_id: JobId) -> None:
        try:
            self._client.delete(self._key(job_id, "progress"), self._key(job_id, "cancel"))
        except RedisError as error:
            raise JobStateStoreError("Не удалось очистить состояние задания") from error

    @staticmethod
    def _key(job_id: JobId, name: str) -> str:
        return f"schedule-job:{job_id}:{name}"
