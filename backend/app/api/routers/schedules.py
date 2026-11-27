from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, UseCasesDep
from app.api.schemas.jobs import QueuedJobResponse, ScheduleResponse
from app.api.schemas.schedules import (
    AutoRepairRequest,
    ReoptimizeRequest,
    ScheduleEntryPatch,
    ScheduleEntryUpdateResponse,
    ScheduleValidationResponse,
)
from app.domain.scheduling.job import JobType, ScheduleEntryPin
from app.domain.shared.ids import ScheduleEntryId, ScheduleId

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.get("/{schedule_id}")
def get_schedule(
    schedule_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> ScheduleResponse:
    return ScheduleResponse.of(use_cases.get_schedule().execute(user_id, ScheduleId(schedule_id)))


@router.patch("/{schedule_id}/entries/{entry_id}")
def update_schedule_entry(
    schedule_id: UUID,
    entry_id: UUID,
    body: ScheduleEntryPatch,
    user_id: CurrentUserDep,
    use_cases: UseCasesDep,
) -> ScheduleEntryUpdateResponse:
    entry, conflicts = use_cases.update_schedule_entry().execute(
        user_id, ScheduleId(schedule_id), ScheduleEntryId(entry_id), body.to_changes()
    )
    return ScheduleEntryUpdateResponse.of(entry, conflicts)


@router.post("/{schedule_id}/validate")
def validate_schedule(
    schedule_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> ScheduleValidationResponse:
    conflicts = use_cases.validate_schedule().execute(user_id, ScheduleId(schedule_id))
    return ScheduleValidationResponse.of(conflicts)


@router.post("/{schedule_id}/auto-repair", status_code=202)
def auto_repair(
    schedule_id: UUID, body: AutoRepairRequest, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> QueuedJobResponse:
    job = use_cases.queue_schedule_processing().execute(
        user_id,
        ScheduleId(schedule_id),
        JobType.AUTO_REPAIR,
        fixed_entry_ids=tuple(ScheduleEntryId(item) for item in body.fixed_entry_ids),
        pins=tuple(
            ScheduleEntryPin(ScheduleEntryId(pin.entry_id), tuple(pin.fields)) for pin in body.pins
        ),
    )
    return QueuedJobResponse.of(job)


@router.post("/{schedule_id}/reoptimize", status_code=202)
def reoptimize(
    schedule_id: UUID, body: ReoptimizeRequest, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> QueuedJobResponse:
    job_type = JobType.REOPTIMIZE_FULL if body.mode == "FULL" else JobType.REOPTIMIZE_MIN_CHANGES
    job = use_cases.queue_schedule_processing().execute(user_id, ScheduleId(schedule_id), job_type)
    return QueuedJobResponse.of(job)
