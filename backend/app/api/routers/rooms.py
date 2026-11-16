from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, UseCasesDep
from app.api.schemas.academic_resources import RoomRequest, RoomResponse, RoomUpdateRequest
from app.domain.shared.ids import ProjectId, RoomId

router = APIRouter(prefix="/projects/{project_id}/rooms", tags=["rooms"])


@router.get("")
def list_rooms(
    project_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> list[RoomResponse]:
    rooms = use_cases.list_rooms().execute(user_id, ProjectId(project_id))
    return [RoomResponse.of(room) for room in rooms]


@router.post("", status_code=201)
def create_room(
    project_id: UUID, body: RoomRequest, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> RoomResponse:
    room = use_cases.create_room().execute(user_id, ProjectId(project_id), body.to_draft())
    return RoomResponse.of(room)


@router.get("/{room_id}")
def get_room(
    project_id: UUID, room_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> RoomResponse:
    room = use_cases.get_room().execute(user_id, ProjectId(project_id), RoomId(room_id))
    return RoomResponse.of(room)


@router.patch("/{room_id}")
def update_room(
    project_id: UUID,
    room_id: UUID,
    body: RoomUpdateRequest,
    user_id: CurrentUserDep,
    use_cases: UseCasesDep,
) -> RoomResponse:
    room = use_cases.update_room().execute(
        user_id, ProjectId(project_id), RoomId(room_id), body.to_changes()
    )
    return RoomResponse.of(room)


@router.delete("/{room_id}", status_code=204)
def delete_room(
    project_id: UUID, room_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> None:
    use_cases.delete_room().execute(user_id, ProjectId(project_id), RoomId(room_id))
