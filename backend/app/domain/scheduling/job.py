from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Self

from app.domain.shared.errors import InvalidValue
from app.domain.shared.ids import JobId, ProjectId


class JobType(StrEnum):
    GENERATE = "GENERATE"
    REOPTIMIZE_FULL = "REOPTIMIZE_FULL"
    REOPTIMIZE_MIN_CHANGES = "REOPTIMIZE_MIN_CHANGES"
    AUTO_REPAIR = "AUTO_REPAIR"


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ResultMode(StrEnum):
    SINGLE = "SINGLE"
    TOP_N = "TOP_N"


@dataclass(frozen=True)
class ResultOptions:
    mode: ResultMode = ResultMode.SINGLE
    top_n: int | None = None

    def __post_init__(self) -> None:
        if self.mode is ResultMode.TOP_N:
            if self.top_n is None or self.top_n <= 0:
                raise InvalidValue("Для TOP_N нужно положительное число вариантов", field="top_n")
        elif self.top_n is not None:
            raise InvalidValue("Число вариантов задаётся только для TOP_N", field="top_n")

    @property
    def limit(self) -> int:
        return self.top_n if self.top_n is not None else 1


@dataclass(frozen=True, kw_only=True)
class Job:
    id: JobId
    project_id: ProjectId
    job_type: JobType
    status: JobStatus
    result_options: ResultOptions
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if self.status is JobStatus.QUEUED and (
            self.started_at is not None or self.finished_at is not None
        ):
            raise InvalidValue("Задание в очереди ещё не начато", field="status")
        if self.status in (JobStatus.RUNNING, JobStatus.COMPLETED) and self.started_at is None:
            raise InvalidValue("Нужно время начала расчёта", field="started_at")
        terminal = self.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)
        if terminal != (self.finished_at is not None):
            raise InvalidValue(
                "Время завершения нужно только конечному статусу", field="finished_at"
            )
        if self.started_at is not None and self.started_at < self.created_at:
            raise InvalidValue("Расчёт не может начаться до создания задания", field="started_at")
        if self.finished_at is not None and self.finished_at < (self.started_at or self.created_at):
            raise InvalidValue("Задание не может завершиться до начала", field="finished_at")

    @property
    def is_terminal(self) -> bool:
        return self.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)

    def start(self, now: datetime) -> Self:
        if self.status is not JobStatus.QUEUED:
            raise InvalidValue("Начать можно только задание в очереди", field="status")
        return replace(self, status=JobStatus.RUNNING, started_at=now)

    def finish(self, status: JobStatus, now: datetime, error_message: str | None = None) -> Self:
        if self.is_terminal or status not in (
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        ):
            raise InvalidValue("Недопустимый переход состояния задания", field="status")
        if status is JobStatus.COMPLETED and self.status is not JobStatus.RUNNING:
            raise InvalidValue("Завершить можно только начатый расчёт", field="status")
        return replace(self, status=status, finished_at=now, error_message=error_message)


@dataclass(frozen=True)
class JobMessage:
    job_id: JobId
    project_id: ProjectId
    job_type: JobType


@dataclass(frozen=True)
class JobProgress:
    percent: float

    def __post_init__(self) -> None:
        if not 0 <= self.percent <= 100:
            raise InvalidValue("Прогресс должен быть от 0 до 100", field="percent")
