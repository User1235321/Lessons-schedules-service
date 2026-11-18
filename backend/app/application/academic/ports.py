from typing import Protocol

from app.domain.academic.group import StudentGroup
from app.domain.academic.room import Room
from app.domain.academic.stream import Stream
from app.domain.academic.subject import Subject
from app.domain.academic.teacher import Teacher
from app.domain.academic.workload import Workload
from app.domain.shared.ids import (
    GroupId,
    ProjectId,
    RoomId,
    StreamId,
    SubgroupId,
    SubjectId,
    TeacherId,
    WorkloadId,
)

# Всё ищется внутри проекта: чужие данные неотличимы от отсутствующих (NF_Security_2).
# Владельца проекта сценарий проверяет раньше, через owned_project.


class SubjectRepository(Protocol):
    def add(self, subject: Subject) -> None:
        """Если в проекте есть дисциплина с таким названием — SubjectNameTaken."""
        ...

    def get(self, project_id: ProjectId, subject_id: SubjectId) -> Subject | None: ...

    def list_in_project(self, project_id: ProjectId) -> list[Subject]:
        """Дисциплины проекта по названию."""
        ...

    def save(self, subject: Subject) -> None:
        """Нет такой дисциплины — NotFound, название занято — SubjectNameTaken."""
        ...

    def delete(self, project_id: ProjectId, subject_id: SubjectId) -> None:
        """Нет такой дисциплины — NotFound.

        Если на неё ссылаются — SubjectInUse, в details списки teachers, rooms и workloads.
        """
        ...


class TeacherRepository(Protocol):
    def add(self, teacher: Teacher) -> None:
        """Если дисциплины из набора нет в проекте — InvalidValue по полю capabilities."""
        ...

    def get(self, project_id: ProjectId, teacher_id: TeacherId) -> Teacher | None: ...

    def get_for_update(self, project_id: ProjectId, teacher_id: TeacherId) -> Teacher | None:
        """Как get, но блокирует преподавателя до конца транзакции: правки идут по очереди."""
        ...

    def list_in_project(self, project_id: ProjectId) -> list[Teacher]:
        """Преподаватели проекта по ФИО."""
        ...

    def save(self, teacher: Teacher) -> None:
        """Нет такого преподавателя — NotFound. Ошибки набора — как в add."""
        ...

    def delete(self, project_id: ProjectId, teacher_id: TeacherId) -> None:
        """Нет такого преподавателя — NotFound."""
        ...


class GroupRepository(Protocol):
    def add(self, group: StudentGroup) -> None:
        """Название занято — GroupNameTaken."""
        ...

    def get(self, project_id: ProjectId, group_id: GroupId) -> StudentGroup | None: ...

    def get_for_update(self, project_id: ProjectId, group_id: GroupId) -> StudentGroup | None:
        """Как get, но блокирует группу до конца транзакции.

        Иначе две параллельные правки подгрупп могли бы вместе нарушить F_Data_12.
        """
        ...

    def get_by_subgroup_for_update(
        self, project_id: ProjectId, subgroup_id: SubgroupId
    ) -> StudentGroup | None:
        """Группа, в которой есть такая подгруппа. Блокируется, как в get_for_update."""
        ...

    def get_by_subgroup(
        self, project_id: ProjectId, subgroup_id: SubgroupId
    ) -> StudentGroup | None:
        """Группа, в которой есть такая подгруппа."""
        ...

    def list_in_project(self, project_id: ProjectId) -> list[StudentGroup]:
        """Группы проекта по названию."""
        ...

    def save(self, group: StudentGroup) -> None:
        """Нет такой группы — NotFound, название занято — GroupNameTaken.

        Подгруппы сохраняются по id: новые добавляются, пропавшие удаляются. Пропавшую
        подгруппу с нагрузкой удалить нельзя — SubgroupInUse, в details список workloads.
        """
        ...

    def delete(self, project_id: ProjectId, group_id: GroupId) -> None:
        """Удаляет группу вместе с подгруппами. Нет такой группы — NotFound.

        Если группа есть в потоках или у неё или её подгрупп есть нагрузка — GroupInUse,
        в details списки streams и workloads.
        """
        ...


class RoomRepository(Protocol):
    def add(self, room: Room) -> None:
        """Название занято — RoomNameTaken, дисциплины из пар нет в проекте — InvalidValue."""
        ...

    def get(self, project_id: ProjectId, room_id: RoomId) -> Room | None: ...

    def get_for_update(self, project_id: ProjectId, room_id: RoomId) -> Room | None:
        """Как get, но блокирует аудиторию до конца транзакции: правки идут по очереди."""
        ...

    def list_in_project(self, project_id: ProjectId) -> list[Room]:
        """Аудитории проекта по названию."""
        ...

    def save(self, room: Room) -> None:
        """Нет такой аудитории — NotFound. Ошибки — как в add."""
        ...

    def delete(self, project_id: ProjectId, room_id: RoomId) -> None:
        """Нет такой аудитории — NotFound."""
        ...


class StreamRepository(Protocol):
    def add(self, stream: Stream) -> None:
        """Название занято — StreamNameTaken, группы нет в проекте — InvalidValue."""
        ...

    def get(self, project_id: ProjectId, stream_id: StreamId) -> Stream | None: ...

    def get_for_update(self, project_id: ProjectId, stream_id: StreamId) -> Stream | None:
        """Как get, но блокирует поток до конца транзакции."""
        ...

    def list_in_project(self, project_id: ProjectId) -> list[Stream]:
        """Потоки проекта по названию."""
        ...

    def save(self, stream: Stream) -> None:
        """Нет такого потока — NotFound. Ошибки — как в add."""
        ...

    def delete(self, project_id: ProjectId, stream_id: StreamId) -> None:
        """Нет такого потока — NotFound. Есть нагрузка потока — StreamInUse."""
        ...


class WorkloadRepository(Protocol):
    def add(self, workload: Workload) -> None:
        """Дисциплины или цели нет в проекте — InvalidValue по subject_id или target.id."""
        ...

    def get(self, project_id: ProjectId, workload_id: WorkloadId) -> Workload | None: ...

    def get_for_update(self, project_id: ProjectId, workload_id: WorkloadId) -> Workload | None:
        """Как get, но блокирует элемент нагрузки до конца транзакции."""
        ...

    def list_in_project(self, project_id: ProjectId) -> list[Workload]:
        """Нагрузка проекта по названию дисциплины и типу занятия."""
        ...

    def save(self, workload: Workload) -> None:
        """Нет такого элемента — NotFound. Ошибки — как в add."""
        ...

    def delete(self, project_id: ProjectId, workload_id: WorkloadId) -> None:
        """Нет такого элемента — NotFound."""
        ...
