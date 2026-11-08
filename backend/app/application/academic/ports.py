from typing import Protocol

from app.domain.academic.group import StudentGroup
from app.domain.academic.subject import Subject
from app.domain.academic.teacher import Teacher
from app.domain.shared.ids import GroupId, ProjectId, SubjectId, TeacherId

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

        Если на неё ссылаются — SubjectInUse, в details список преподавателей.
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

    def list_in_project(self, project_id: ProjectId) -> list[StudentGroup]:
        """Группы проекта по названию."""
        ...

    def save(self, group: StudentGroup) -> None:
        """Нет такой группы — NotFound, название занято — GroupNameTaken.

        Подгруппы сохраняются по id: новые добавляются, пропавшие удаляются.
        """
        ...

    def delete(self, project_id: ProjectId, group_id: GroupId) -> None:
        """Удаляет группу вместе с подгруппами. Нет такой группы — NotFound."""
        ...
