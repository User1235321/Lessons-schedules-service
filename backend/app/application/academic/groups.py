from dataclasses import dataclass

from app.application.academic.changes import project_data_changed
from app.application.auth.access import owned_project
from app.application.shared.ports import Clock, IdGenerator
from app.application.shared.uow import UnitOfWork
from app.domain.academic.group import StudentGroup, Subgroup
from app.domain.shared.errors import InvalidValue, NotFound
from app.domain.shared.ids import GroupId, ProjectId, SubgroupId, UserId


@dataclass(frozen=True)
class SubgroupInGroup:
    """Подгруппа вместе с id своей группы: так её отдаёт API подгрупп."""

    group_id: GroupId
    subgroup: Subgroup


def _group_not_found(group_id: GroupId) -> NotFound:
    return NotFound("Группа не найдена", group_id=str(group_id))


def _subgroup_not_found(subgroup_id: SubgroupId) -> NotFound:
    return NotFound("Подгруппа не найдена", subgroup_id=str(subgroup_id))


@dataclass(frozen=True)
class CreateGroup:
    """Новая группа без подгрупп: подгруппы добавляются отдельно."""

    uow: UnitOfWork
    clock: Clock
    ids: IdGenerator

    def execute(
        self, user_id: UserId, project_id: ProjectId, name: str, student_count: int
    ) -> StudentGroup:
        with self.uow:
            project = owned_project(self.uow, project_id, user_id)
            group = StudentGroup(
                id=GroupId(self.ids.new_id()),
                project_id=project.id,
                name=name,
                student_count=student_count,
            )
            self.uow.groups.add(group)
            project_data_changed(self.uow, project, self.clock.now())
            self.uow.commit()
        return group


@dataclass(frozen=True)
class ListGroups:
    uow: UnitOfWork

    def execute(self, user_id: UserId, project_id: ProjectId) -> list[StudentGroup]:
        with self.uow:
            owned_project(self.uow, project_id, user_id)
            return self.uow.groups.list_in_project(project_id)


@dataclass(frozen=True)
class GetGroup:
    uow: UnitOfWork

    def execute(self, user_id: UserId, project_id: ProjectId, group_id: GroupId) -> StudentGroup:
        with self.uow:
            owned_project(self.uow, project_id, user_id)
            group = self.uow.groups.get(project_id, group_id)
        if group is None:
            raise _group_not_found(group_id)
        return group


@dataclass(frozen=True)
class UpdateGroup:
    uow: UnitOfWork
    clock: Clock

    def execute(
        self,
        user_id: UserId,
        project_id: ProjectId,
        group_id: GroupId,
        name: str | None,
        student_count: int | None,
    ) -> StudentGroup:
        with self.uow:
            project = owned_project(self.uow, project_id, user_id)
            group = self.uow.groups.get_for_update(project_id, group_id)
            if group is None:
                raise _group_not_found(group_id)
            if name is None and student_count is None:
                return group
            if name is not None:
                group.rename(name)
            if student_count is not None:
                group.change_student_count(student_count)  # F_Data_12
            self.uow.groups.save(group)
            project_data_changed(self.uow, project, self.clock.now())
            self.uow.commit()
        return group


@dataclass(frozen=True)
class DeleteGroup:
    """Группа удаляется вместе с подгруппами."""

    uow: UnitOfWork
    clock: Clock

    def execute(self, user_id: UserId, project_id: ProjectId, group_id: GroupId) -> None:
        with self.uow:
            project = owned_project(self.uow, project_id, user_id)
            self.uow.groups.delete(project_id, group_id)
            project_data_changed(self.uow, project, self.clock.now())
            self.uow.commit()


@dataclass(frozen=True)
class CreateSubgroup:
    """Новая подгруппа (F_Data_11). Группа блокируется, чтобы проверка F_Data_12 не устарела."""

    uow: UnitOfWork
    clock: Clock
    ids: IdGenerator

    def execute(
        self,
        user_id: UserId,
        project_id: ProjectId,
        group_id: GroupId,
        name: str,
        student_count: int,
    ) -> SubgroupInGroup:
        with self.uow:
            project = owned_project(self.uow, project_id, user_id)
            group = self.uow.groups.get_for_update(project_id, group_id)
            if group is None:
                # Группа пришла в теле запроса, а не в адресе: это ошибка ввода
                raise InvalidValue("Такой группы нет в проекте", field="group_id")
            subgroup = Subgroup(
                id=SubgroupId(self.ids.new_id()), name=name, student_count=student_count
            )
            group.add_subgroup(subgroup)
            self.uow.groups.save(group)
            project_data_changed(self.uow, project, self.clock.now())
            self.uow.commit()
        return SubgroupInGroup(group.id, subgroup)


@dataclass(frozen=True)
class ListSubgroups:
    """Подгруппы проекта по группам и названиям. С group_id — только этой группы."""

    uow: UnitOfWork

    def execute(
        self, user_id: UserId, project_id: ProjectId, group_id: GroupId | None
    ) -> list[SubgroupInGroup]:
        with self.uow:
            owned_project(self.uow, project_id, user_id)
            if group_id is None:
                groups = self.uow.groups.list_in_project(project_id)
            else:
                group = self.uow.groups.get(project_id, group_id)
                if group is None:
                    raise _group_not_found(group_id)
                groups = [group]
        return [
            SubgroupInGroup(group.id, subgroup) for group in groups for subgroup in group.subgroups
        ]


@dataclass(frozen=True)
class GetSubgroup:
    uow: UnitOfWork

    def execute(
        self, user_id: UserId, project_id: ProjectId, subgroup_id: SubgroupId
    ) -> SubgroupInGroup:
        with self.uow:
            owned_project(self.uow, project_id, user_id)
            group = self.uow.groups.get_by_subgroup(project_id, subgroup_id)
        if group is None:
            raise _subgroup_not_found(subgroup_id)
        return SubgroupInGroup(group.id, group.subgroup(subgroup_id))


@dataclass(frozen=True)
class UpdateSubgroup:
    uow: UnitOfWork
    clock: Clock

    def execute(
        self,
        user_id: UserId,
        project_id: ProjectId,
        subgroup_id: SubgroupId,
        name: str | None,
        student_count: int | None,
    ) -> SubgroupInGroup:
        with self.uow:
            project = owned_project(self.uow, project_id, user_id)
            group = self.uow.groups.get_by_subgroup_for_update(project_id, subgroup_id)
            if group is None:
                raise _subgroup_not_found(subgroup_id)
            current = group.subgroup(subgroup_id)
            if name is None and student_count is None:
                return SubgroupInGroup(group.id, current)
            changed = Subgroup(
                id=subgroup_id,
                name=current.name if name is None else name,
                student_count=current.student_count if student_count is None else student_count,
            )
            group.change_subgroup(changed)  # F_Data_12
            self.uow.groups.save(group)
            project_data_changed(self.uow, project, self.clock.now())
            self.uow.commit()
        return SubgroupInGroup(group.id, group.subgroup(subgroup_id))


@dataclass(frozen=True)
class DeleteSubgroup:
    uow: UnitOfWork
    clock: Clock

    def execute(self, user_id: UserId, project_id: ProjectId, subgroup_id: SubgroupId) -> None:
        with self.uow:
            project = owned_project(self.uow, project_id, user_id)
            group = self.uow.groups.get_by_subgroup_for_update(project_id, subgroup_id)
            if group is None:
                raise _subgroup_not_found(subgroup_id)
            group.remove_subgroup(subgroup_id)
            self.uow.groups.save(group)
            project_data_changed(self.uow, project, self.clock.now())
            self.uow.commit()
