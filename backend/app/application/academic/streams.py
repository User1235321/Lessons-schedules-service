from dataclasses import dataclass

from app.application.academic.changes import project_data_changed
from app.application.auth.access import owned_project
from app.application.constraints.references import ensure_not_referenced
from app.application.shared.ports import Clock, IdGenerator
from app.application.shared.uow import UnitOfWork
from app.domain.academic.stream import Stream
from app.domain.shared.errors import InvalidValue, NotFound
from app.domain.shared.ids import GroupId, ProjectId, StreamId, UserId


@dataclass(frozen=True)
class StreamDraft:
    name: str
    group_ids: tuple[GroupId, ...]


@dataclass(frozen=True)
class StreamChanges:
    name: str | None = None
    group_ids: tuple[GroupId, ...] | None = None


def _check_groups(uow: UnitOfWork, project_id: ProjectId, group_ids: tuple[GroupId, ...]) -> None:
    available = {group.id for group in uow.groups.list_in_project(project_id)}
    for index, group_id in enumerate(group_ids):
        if group_id not in available:
            raise InvalidValue("Такой группы нет в проекте", field=f"group_ids.{index}")


def _not_found(stream_id: StreamId) -> NotFound:
    return NotFound("Поток не найден", stream_id=str(stream_id))


@dataclass(frozen=True)
class CreateStream:
    uow: UnitOfWork
    clock: Clock
    ids: IdGenerator

    def execute(self, user_id: UserId, project_id: ProjectId, draft: StreamDraft) -> Stream:
        with self.uow:
            project = owned_project(self.uow, project_id, user_id)
            _check_groups(self.uow, project_id, draft.group_ids)
            stream = Stream(
                id=StreamId(self.ids.new_id()),
                project_id=project.id,
                name=draft.name,
                group_ids=draft.group_ids,
            )
            self.uow.streams.add(stream)
            project_data_changed(self.uow, project, self.clock.now())
            self.uow.commit()
        return stream


@dataclass(frozen=True)
class ListStreams:
    uow: UnitOfWork

    def execute(self, user_id: UserId, project_id: ProjectId) -> list[Stream]:
        with self.uow:
            owned_project(self.uow, project_id, user_id)
            return self.uow.streams.list_in_project(project_id)


@dataclass(frozen=True)
class GetStream:
    uow: UnitOfWork

    def execute(self, user_id: UserId, project_id: ProjectId, stream_id: StreamId) -> Stream:
        with self.uow:
            owned_project(self.uow, project_id, user_id)
            stream = self.uow.streams.get(project_id, stream_id)
        if stream is None:
            raise _not_found(stream_id)
        return stream


@dataclass(frozen=True)
class UpdateStream:
    uow: UnitOfWork
    clock: Clock

    def execute(
        self, user_id: UserId, project_id: ProjectId, stream_id: StreamId, changes: StreamChanges
    ) -> Stream:
        with self.uow:
            project = owned_project(self.uow, project_id, user_id)
            stream = self.uow.streams.get_for_update(project_id, stream_id)
            if stream is None:
                raise _not_found(stream_id)
            if changes == StreamChanges():
                return stream
            if changes.group_ids is not None:
                _check_groups(self.uow, project_id, changes.group_ids)
                stream.change_groups(changes.group_ids)
            if changes.name is not None:
                stream.rename(changes.name)
            self.uow.streams.save(stream)
            project_data_changed(self.uow, project, self.clock.now())
            self.uow.commit()
        return stream


@dataclass(frozen=True)
class DeleteStream:
    uow: UnitOfWork
    clock: Clock

    def execute(self, user_id: UserId, project_id: ProjectId, stream_id: StreamId) -> None:
        with self.uow:
            project = owned_project(self.uow, project_id, user_id)
            if self.uow.streams.get_for_update(project_id, stream_id) is None:
                raise _not_found(stream_id)
            ensure_not_referenced(self.uow, project_id, "STREAM", {stream_id})
            self.uow.streams.delete(project_id, stream_id)
            project_data_changed(self.uow, project, self.clock.now())
            self.uow.commit()
