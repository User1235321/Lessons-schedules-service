from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, UseCasesDep
from app.api.schemas.academic_resources import StreamRequest, StreamResponse, StreamUpdateRequest
from app.domain.shared.ids import ProjectId, StreamId

router = APIRouter(prefix="/projects/{project_id}/streams", tags=["streams"])


@router.get("")
def list_streams(
    project_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> list[StreamResponse]:
    streams = use_cases.list_streams().execute(user_id, ProjectId(project_id))
    return [StreamResponse.of(stream) for stream in streams]


@router.post("", status_code=201)
def create_stream(
    project_id: UUID, body: StreamRequest, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> StreamResponse:
    stream = use_cases.create_stream().execute(user_id, ProjectId(project_id), body.to_draft())
    return StreamResponse.of(stream)


@router.get("/{stream_id}")
def get_stream(
    project_id: UUID, stream_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> StreamResponse:
    stream = use_cases.get_stream().execute(user_id, ProjectId(project_id), StreamId(stream_id))
    return StreamResponse.of(stream)


@router.patch("/{stream_id}")
def update_stream(
    project_id: UUID,
    stream_id: UUID,
    body: StreamUpdateRequest,
    user_id: CurrentUserDep,
    use_cases: UseCasesDep,
) -> StreamResponse:
    stream = use_cases.update_stream().execute(
        user_id, ProjectId(project_id), StreamId(stream_id), body.to_changes()
    )
    return StreamResponse.of(stream)


@router.delete("/{stream_id}", status_code=204)
def delete_stream(
    project_id: UUID, stream_id: UUID, user_id: CurrentUserDep, use_cases: UseCasesDep
) -> None:
    use_cases.delete_stream().execute(user_id, ProjectId(project_id), StreamId(stream_id))
