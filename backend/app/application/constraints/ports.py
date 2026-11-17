from typing import Protocol
from uuid import UUID

from app.domain.scheduling.constraints import ExtraConstraintSnapshot
from app.domain.scheduling.problem import OptimizationCriterionSnapshot
from app.domain.shared.ids import ProjectId


class ConstraintRepository(Protocol):
    def add(self, project_id: ProjectId, constraint: ExtraConstraintSnapshot) -> None: ...

    def get(self, project_id: ProjectId, constraint_id: UUID) -> ExtraConstraintSnapshot | None: ...

    def get_for_update(
        self, project_id: ProjectId, constraint_id: UUID
    ) -> ExtraConstraintSnapshot | None: ...

    def list_in_project(self, project_id: ProjectId) -> list[ExtraConstraintSnapshot]: ...

    def save(self, project_id: ProjectId, constraint: ExtraConstraintSnapshot) -> None: ...

    def delete(self, project_id: ProjectId, constraint_id: UUID) -> None: ...

    def referencing(
        self, project_id: ProjectId, resource_type: str, resource_ids: set[UUID]
    ) -> list[UUID]: ...


class CriterionRepository(Protocol):
    def list_in_project(self, project_id: ProjectId) -> list[OptimizationCriterionSnapshot]: ...

    def replace(
        self, project_id: ProjectId, criteria: tuple[OptimizationCriterionSnapshot, ...]
    ) -> None: ...
