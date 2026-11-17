from uuid import UUID

from sqlalchemy import delete, insert, or_, select, update
from sqlalchemy.orm import Session

from app.application.constraints.codec import (
    parameters_to_json,
    parse_parameters,
    scope_from_json,
    scope_to_json,
)
from app.domain.scheduling.constraints import ConstraintKind, ExtraConstraintSnapshot
from app.domain.scheduling.problem import OptimizationCriterionSnapshot
from app.domain.shared.errors import NotFound
from app.domain.shared.ids import ProjectId
from app.infrastructure.persistence.models.constraints import (
    ExtraConstraintRow,
    OptimizationCriterionRow,
)
from app.infrastructure.persistence.models.projects import ProjectRow


def _constraint_to_domain(row: ExtraConstraintRow) -> ExtraConstraintSnapshot:
    kind = ConstraintKind(row.constraint_type)
    return ExtraConstraintSnapshot(
        id=row.id,
        kind=kind,
        scope=scope_from_json(row.scope),
        parameters=parse_parameters(kind, row.parameters),
    )


def _values(constraint: ExtraConstraintSnapshot) -> dict[str, object]:
    return {
        "constraint_type": constraint.kind.value,
        "scope": scope_to_json(constraint.scope),
        "parameters": parameters_to_json(constraint.parameters),
    }


class SqlConstraintRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, project_id: ProjectId, constraint: ExtraConstraintSnapshot) -> None:
        self._session.execute(
            insert(ExtraConstraintRow).values(
                id=constraint.id, project_id=project_id, **_values(constraint)
            )
        )

    def get(self, project_id: ProjectId, constraint_id: UUID) -> ExtraConstraintSnapshot | None:
        row = self._session.scalar(
            select(ExtraConstraintRow).where(
                ExtraConstraintRow.project_id == project_id, ExtraConstraintRow.id == constraint_id
            )
        )
        return _constraint_to_domain(row) if row else None

    def get_for_update(
        self, project_id: ProjectId, constraint_id: UUID
    ) -> ExtraConstraintSnapshot | None:
        row = self._session.scalar(
            select(ExtraConstraintRow).where(
                ExtraConstraintRow.project_id == project_id, ExtraConstraintRow.id == constraint_id
            ).with_for_update()
        )
        return _constraint_to_domain(row) if row else None

    def list_in_project(self, project_id: ProjectId) -> list[ExtraConstraintSnapshot]:
        rows = self._session.scalars(
            select(ExtraConstraintRow)
            .where(ExtraConstraintRow.project_id == project_id)
            .order_by(ExtraConstraintRow.id)
        )
        return [_constraint_to_domain(row) for row in rows]

    def save(self, project_id: ProjectId, constraint: ExtraConstraintSnapshot) -> None:
        updated = self._session.scalar(
            update(ExtraConstraintRow)
            .where(
                ExtraConstraintRow.project_id == project_id,
                ExtraConstraintRow.id == constraint.id,
            )
            .values(_values(constraint))
            .returning(ExtraConstraintRow.id)
        )
        if updated is None:
            raise NotFound("Ограничение не найдено", constraint_id=str(constraint.id))

    def delete(self, project_id: ProjectId, constraint_id: UUID) -> None:
        deleted = self._session.scalar(
            delete(ExtraConstraintRow)
            .where(
                ExtraConstraintRow.project_id == project_id,
                ExtraConstraintRow.id == constraint_id,
            )
            .returning(ExtraConstraintRow.id)
        )
        if deleted is None:
            raise NotFound("Ограничение не найдено", constraint_id=str(constraint_id))

    def referencing(
        self, project_id: ProjectId, resource_type: str, resource_ids: set[UUID]
    ) -> list[UUID]:
        if not resource_ids:
            return []
        ids = [str(resource_id) for resource_id in resource_ids]
        expressions = [
            (ExtraConstraintRow.scope["type"].as_string() == resource_type)
            & (ExtraConstraintRow.scope["id"].as_string().in_(ids))
        ]
        if resource_type == "WORKLOAD":
            expressions.append(ExtraConstraintRow.parameters["workload_id"].as_string().in_(ids))
        return list(
            self._session.scalars(
                select(ExtraConstraintRow.id)
                .where(ExtraConstraintRow.project_id == project_id, or_(*expressions))
                .order_by(ExtraConstraintRow.id)
            )
        )


class SqlCriterionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_in_project(self, project_id: ProjectId) -> list[OptimizationCriterionSnapshot]:
        rows = self._session.scalars(
            select(OptimizationCriterionRow)
            .where(OptimizationCriterionRow.project_id == project_id)
            .order_by(OptimizationCriterionRow.priority, OptimizationCriterionRow.criterion_type)
        )
        return [
            OptimizationCriterionSnapshot(row.criterion_type, row.priority, row.is_active)
            for row in rows
        ]

    def replace(
        self, project_id: ProjectId, criteria: tuple[OptimizationCriterionSnapshot, ...]
    ) -> None:
        self._session.execute(
            select(ProjectRow.id).where(ProjectRow.id == project_id).with_for_update()
        ).scalar_one()
        self._session.execute(
            delete(OptimizationCriterionRow).where(OptimizationCriterionRow.project_id == project_id)
        )
        if criteria:
            self._session.execute(
                insert(OptimizationCriterionRow),
                [
                    {
                        "project_id": project_id,
                        "criterion_type": criterion.criterion_type,
                        "priority": criterion.priority,
                        "is_active": criterion.is_active,
                    }
                    for criterion in criteria
                ],
            )
