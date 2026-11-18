from dataclasses import dataclass

from app.application.academic.changes import project_data_changed
from app.application.auth.access import owned_project
from app.application.shared.ports import Clock, IdGenerator
from app.application.shared.uow import UnitOfWork
from app.domain.academic.capability import Capability
from app.domain.academic.room import Room, RoomType
from app.domain.shared.errors import InvalidValue, NotFound
from app.domain.shared.ids import ProjectId, RoomId, UserId
from app.domain.shared.week import WeeklyInterval


@dataclass(frozen=True)
class RoomDraft:
    name: str
    capacity: int
    room_type: RoomType
    availability: tuple[WeeklyInterval, ...]
    capabilities: tuple[Capability, ...] = ()


@dataclass(frozen=True)
class RoomChanges:
    name: str | None = None
    capacity: int | None = None
    room_type: RoomType | None = None
    availability: tuple[WeeklyInterval, ...] | None = None
    capabilities: tuple[Capability, ...] | None = None


def _check_subjects(
    uow: UnitOfWork, project_id: ProjectId, capabilities: tuple[Capability, ...]
) -> None:
    available = {subject.id for subject in uow.subjects.list_in_project(project_id)}
    for index, capability in enumerate(capabilities):
        if capability.subject_id not in available:
            raise InvalidValue(
                "Такой дисциплины нет в проекте",
                field=f"capabilities.{index}.subject_id",
            )


def _not_found(room_id: RoomId) -> NotFound:
    return NotFound("Аудитория не найдена", room_id=str(room_id))


@dataclass(frozen=True)
class CreateRoom:
    uow: UnitOfWork
    clock: Clock
    ids: IdGenerator

    def execute(self, user_id: UserId, project_id: ProjectId, draft: RoomDraft) -> Room:
        with self.uow:
            project = owned_project(self.uow, project_id, user_id)
            _check_subjects(self.uow, project_id, draft.capabilities)
            room = Room(
                id=RoomId(self.ids.new_id()),
                project_id=project.id,
                name=draft.name,
                capacity=draft.capacity,
                type=draft.room_type,
                availability=draft.availability,
                capabilities=draft.capabilities,
            )
            self.uow.rooms.add(room)
            project_data_changed(self.uow, project, self.clock.now())
            self.uow.commit()
        return room


@dataclass(frozen=True)
class ListRooms:
    uow: UnitOfWork

    def execute(self, user_id: UserId, project_id: ProjectId) -> list[Room]:
        with self.uow:
            owned_project(self.uow, project_id, user_id)
            return self.uow.rooms.list_in_project(project_id)


@dataclass(frozen=True)
class GetRoom:
    uow: UnitOfWork

    def execute(self, user_id: UserId, project_id: ProjectId, room_id: RoomId) -> Room:
        with self.uow:
            owned_project(self.uow, project_id, user_id)
            room = self.uow.rooms.get(project_id, room_id)
        if room is None:
            raise _not_found(room_id)
        return room


@dataclass(frozen=True)
class UpdateRoom:
    uow: UnitOfWork
    clock: Clock

    def execute(
        self, user_id: UserId, project_id: ProjectId, room_id: RoomId, changes: RoomChanges
    ) -> Room:
        with self.uow:
            project = owned_project(self.uow, project_id, user_id)
            room = self.uow.rooms.get_for_update(project_id, room_id)
            if room is None:
                raise _not_found(room_id)
            if changes == RoomChanges():
                return room
            if changes.name is not None:
                room.rename(changes.name)
            if changes.capacity is not None:
                room.change_capacity(changes.capacity)
            if changes.availability is not None:
                room.change_availability(changes.availability)
            if changes.capabilities is not None:
                _check_subjects(self.uow, project_id, changes.capabilities)
            if changes.room_type is not None or changes.capabilities is not None:
                room.change_type(
                    changes.room_type if changes.room_type is not None else room.type,
                    changes.capabilities if changes.capabilities is not None else room.capabilities,
                )
            self.uow.rooms.save(room)
            project_data_changed(self.uow, project, self.clock.now())
            self.uow.commit()
        return room


@dataclass(frozen=True)
class DeleteRoom:
    uow: UnitOfWork
    clock: Clock

    def execute(self, user_id: UserId, project_id: ProjectId, room_id: RoomId) -> None:
        with self.uow:
            project = owned_project(self.uow, project_id, user_id)
            self.uow.rooms.delete(project_id, room_id)
            project_data_changed(self.uow, project, self.clock.now())
            self.uow.commit()
