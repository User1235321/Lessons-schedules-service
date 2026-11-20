from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, UseCasesDep
from app.api.schemas.jobs import ScheduleResponse
from app.api.schemas.schedules import (
    ScheduleEntryPatch,
    ScheduleEntryUpdateResponse,
    ScheduleValidationResponse,
)
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
