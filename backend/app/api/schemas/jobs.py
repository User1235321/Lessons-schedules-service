from datetime import datetime, time
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.application.scheduling.use_cases import JobView
from app.domain.scheduling.job import Job, JobStatus, JobType, ResultMode, ResultOptions
from app.domain.scheduling.schedule import LessonFormat, Schedule, ScheduleSource
from app.domain.shared.week import Weekday


class TeacherAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    teacher_id: UUID | None
    display_name: str


class ScheduleEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workload_id: UUID | None
    subject_name: str | None
    participant_label: str | None
    lesson_type: Literal["LECTURE", "PRACTICE", "LAB"] | None
    lesson_format: LessonFormat | None
    week: Literal["ODD", "EVEN"]
    weekday: Weekday
    start_time: time
    end_time: time
    room_id: UUID | None
    room_name: str | None
    teachers: list[TeacherAssignmentResponse]

    @field_serializer("start_time", "end_time")
    def serialize_time(self, value: time) -> str:
        return value.strftime("%H:%M")


class ScheduleResponse(BaseModel):
    id: UUID
    project_id: UUID
    source: ScheduleSource
    job_id: UUID | None
    result_index: int | None
    criterion_scores: dict[str, float] | None
    entries: list[ScheduleEntryResponse]

    @classmethod
    def of(cls, schedule: Schedule) -> Self:
        return cls(
            id=schedule.id,
            project_id=schedule.project_id,
            source=schedule.source,
            job_id=schedule.job_id,
            result_index=schedule.result_index,
            criterion_scores=(
                {score.criterion: score.value for score in schedule.criterion_scores}
                if schedule.criterion_scores is not None
                else None
            ),
            entries=[
                ScheduleEntryResponse.model_validate(entry) for entry in schedule.entries
            ],
        )


class GenerationJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_mode: ResultMode = ResultMode.SINGLE
    top_n: int | None = Field(default=None, strict=True, gt=0)

    def to_options(self) -> ResultOptions:
        return ResultOptions(self.result_mode, self.top_n)


class QueuedJobResponse(BaseModel):
    job_id: UUID
    status: Literal[JobStatus.QUEUED] = JobStatus.QUEUED

    @classmethod
    def of(cls, job: Job) -> Self:
        return cls(job_id=job.id)


class JobResponse(BaseModel):
    id: UUID
    project_id: UUID
    job_type: JobType
    status: JobStatus
    progress: float | None
    error_message: str | None

    @classmethod
    def of(cls, view: JobView) -> Self:
        return cls(
            id=view.job.id,
            project_id=view.job.project_id,
            job_type=view.job.job_type,
            status=view.job.status,
            progress=view.progress.percent if view.progress else None,
            error_message=view.job.error_message,
        )
