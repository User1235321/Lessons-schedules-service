from dataclasses import dataclass
from uuid import UUID

from app.application.academic.changes import project_data_changed
from app.application.auth.access import owned_project
from app.application.constraints.codec import parse_parameters
from app.application.shared.ports import Clock, IdGenerator
from app.application.shared.uow import UnitOfWork
from app.domain.scheduling.constraints import (
    ConstraintKind,
    ConstraintParameters,
    ConstraintScope,
    ConstraintScopeKind,
    ExtraConstraintSnapshot,
    MinimumGapParameters,
    RelatedWorkloadParameters,
)
from app.domain.scheduling.problem import OptimizationCriterionSnapshot
from app.domain.shared.errors import InvalidValue, NotFound
from app.domain.shared.ids import GroupId, ProjectId, StreamId, SubgroupId, UserId, WorkloadId

_WORKLOAD_SCOPES = {
    ConstraintKind.EVERY_WEEK,
    ConstraintKind.CONSECUTIVE,
    ConstraintKind.NOT_CONSECUTIVE,
    ConstraintKind.MIN_GAP,
    ConstraintKind.BEFORE,
    ConstraintKind.FIXED_DAY,
}


@dataclass(frozen=True)
class ConstraintDraft:
    kind: ConstraintKind
    scope: ConstraintScope
    parameters: ConstraintParameters


@dataclass(frozen=True)
class ConstraintChanges:
    kind: ConstraintKind | None = None
    scope: ConstraintScope | None = None
    parameters: dict[str, object] | None = None


def _validate_references(
    uow: UnitOfWork, project_id: ProjectId, constraint: ExtraConstraintSnapshot
) -> None:
    scope = constraint.scope
    if constraint.kind in _WORKLOAD_SCOPES and scope.kind is not ConstraintScopeKind.WORKLOAD:
        raise InvalidValue("Ограничение применяется к учебной нагрузке", field="scope.type")

    resource = None
    if scope.kind is ConstraintScopeKind.GROUP:
        resource = uow.groups.get(project_id, GroupId(scope.resource_id))
    elif scope.kind is ConstraintScopeKind.SUBGROUP:
        resource = uow.groups.get_by_subgroup(project_id, SubgroupId(scope.resource_id))
    elif scope.kind is ConstraintScopeKind.STREAM:
        resource = uow.streams.get(project_id, StreamId(scope.resource_id))
    elif scope.kind is ConstraintScopeKind.WORKLOAD:
        resource = uow.workloads.get(project_id, WorkloadId(scope.resource_id))
    if scope.kind is not ConstraintScopeKind.PROJECT and resource is None:
        raise InvalidValue("Ресурс не найден в проекте", field="scope.id")

    if isinstance(constraint.parameters, (RelatedWorkloadParameters, MinimumGapParameters)):
        if uow.workloads.get(project_id, WorkloadId(constraint.parameters.workload_id)) is None:
            raise InvalidValue(
                "Связанная учебная нагрузка не найдена", field="parameters.workload_id"
            )


def _not_found(constraint_id: UUID) -> NotFound:
    return NotFound("Ограничение не найдено", constraint_id=str(constraint_id))


@dataclass(frozen=True)
class CreateConstraint:
    uow: UnitOfWork
    clock: Clock
    ids: IdGenerator

    def execute(
        self, user_id: UserId, project_id: ProjectId, draft: ConstraintDraft
    ) -> ExtraConstraintSnapshot:
        with self.uow:
            project = owned_project(self.uow, project_id, user_id)
            constraint = ExtraConstraintSnapshot(
                self.ids.new_id(), draft.kind, draft.scope, draft.parameters
            )
            self.uow.constraints.lock_project(project_id)
            _validate_references(self.uow, project_id, constraint)
            self.uow.constraints.add(project_id, constraint)
            project_data_changed(self.uow, project, self.clock.now())
            self.uow.commit()
            return constraint


@dataclass(frozen=True)
class ListConstraints:
    uow: UnitOfWork

    def execute(
        self, user_id: UserId, project_id: ProjectId
    ) -> list[ExtraConstraintSnapshot]:
        with self.uow:
            owned_project(self.uow, project_id, user_id)
            return self.uow.constraints.list_in_project(project_id)


@dataclass(frozen=True)
class UpdateConstraint:
    uow: UnitOfWork
    clock: Clock

    def execute(
        self,
        user_id: UserId,
        project_id: ProjectId,
        constraint_id: UUID,
        changes: ConstraintChanges,
    ) -> ExtraConstraintSnapshot:
        with self.uow:
            project = owned_project(self.uow, project_id, user_id)
            self.uow.constraints.lock_project(project_id)
            current = self.uow.constraints.get_for_update(project_id, constraint_id)
            if current is None:
                raise _not_found(constraint_id)
            kind = changes.kind if changes.kind is not None else current.kind
            scope = changes.scope if changes.scope is not None else current.scope
            params = (
                parse_parameters(kind, changes.parameters)
                if changes.parameters is not None else current.parameters
            )
            updated = ExtraConstraintSnapshot(current.id, kind, scope, params)
            if updated != current:
                _validate_references(self.uow, project_id, updated)
                self.uow.constraints.save(project_id, updated)
                project_data_changed(self.uow, project, self.clock.now())
                self.uow.commit()
            return updated


@dataclass(frozen=True)
class DeleteConstraint:
    uow: UnitOfWork
    clock: Clock

    def execute(self, user_id: UserId, project_id: ProjectId, constraint_id: UUID) -> None:
        with self.uow:
            project = owned_project(self.uow, project_id, user_id)
            self.uow.constraints.lock_project(project_id)
            self.uow.constraints.delete(project_id, constraint_id)
            project_data_changed(self.uow, project, self.clock.now())
            self.uow.commit()


@dataclass(frozen=True)
class ListCriteria:
    uow: UnitOfWork

    def execute(
        self, user_id: UserId, project_id: ProjectId
    ) -> list[OptimizationCriterionSnapshot]:
        with self.uow:
            owned_project(self.uow, project_id, user_id)
            return self.uow.criteria.list_in_project(project_id)


def _validate_criteria(criteria: tuple[OptimizationCriterionSnapshot, ...]) -> None:
    types = [item.criterion_type for item in criteria]
    if len(types) != len(set(types)):
        raise InvalidValue("Критерий оптимизации задан повторно", field="criteria")
    priorities = [item.priority for item in criteria if item.is_active]
    if len(priorities) != len(set(priorities)):
        raise InvalidValue("Приоритеты активных критериев должны отличаться", field="criteria")


@dataclass(frozen=True)
class ReplaceCriteria:
    uow: UnitOfWork
    clock: Clock

    def execute(
        self,
        user_id: UserId,
        project_id: ProjectId,
        criteria: tuple[OptimizationCriterionSnapshot, ...],
    ) -> list[OptimizationCriterionSnapshot]:
        _validate_criteria(criteria)
        with self.uow:
            project = owned_project(self.uow, project_id, user_id)
            self.uow.criteria.replace(project_id, criteria)
            project_data_changed(self.uow, project, self.clock.now())
            self.uow.commit()
            return self.uow.criteria.list_in_project(project_id)
