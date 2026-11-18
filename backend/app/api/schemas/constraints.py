from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.application.constraints.codec import parameters_to_json, parse_parameters
from app.application.constraints.use_cases import ConstraintChanges, ConstraintDraft
from app.domain.scheduling.constraints import (
    ConstraintKind,
    ConstraintScope,
    ConstraintScopeKind,
    ExtraConstraintSnapshot,
)
from app.domain.scheduling.problem import CriterionType, OptimizationCriterionSnapshot


class ConstraintSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScopeSchema(ConstraintSchema):
    type: ConstraintScopeKind
    id: UUID | None = None

    def to_domain(self) -> ConstraintScope:
        return ConstraintScope(self.type, self.id)

    @classmethod
    def of(cls, scope: ConstraintScope) -> "ScopeSchema":
        return cls(type=scope.kind, id=scope.resource_id)


class CreateConstraintRequest(ConstraintSchema):
    constraint_type: ConstraintKind
    scope: ScopeSchema
    parameters: dict[str, object]

    def to_draft(self) -> ConstraintDraft:
        return ConstraintDraft(
            kind=self.constraint_type,
            scope=self.scope.to_domain(),
            parameters=parse_parameters(self.constraint_type, self.parameters),
        )


class UpdateConstraintRequest(ConstraintSchema):
    constraint_type: ConstraintKind | None = None
    scope: ScopeSchema | None = None
    parameters: dict[str, object] | None = None

    def to_changes(self) -> ConstraintChanges:
        return ConstraintChanges(
            kind=self.constraint_type,
            scope=self.scope.to_domain() if self.scope is not None else None,
            parameters=self.parameters,
        )


class ConstraintResponse(ConstraintSchema):
    id: UUID
    project_id: UUID
    constraint_type: ConstraintKind
    scope: ScopeSchema
    parameters: dict[str, object]

    @classmethod
    def of(cls, project_id: UUID, constraint: ExtraConstraintSnapshot) -> "ConstraintResponse":
        return cls(
            id=constraint.id,
            project_id=project_id,
            constraint_type=constraint.kind,
            scope=ScopeSchema.of(constraint.scope),
            parameters=parameters_to_json(constraint.parameters),
        )


class CriterionSchema(ConstraintSchema):
    criterion_type: CriterionType
    priority: int = Field(gt=0, le=2**31 - 1)
    is_active: bool = True

    def to_domain(self) -> OptimizationCriterionSnapshot:
        return OptimizationCriterionSnapshot(
            self.criterion_type, self.priority, self.is_active
        )

    @classmethod
    def of(cls, criterion: OptimizationCriterionSnapshot) -> "CriterionSchema":
        return cls(
            criterion_type=criterion.criterion_type,
            priority=criterion.priority,
            is_active=criterion.is_active,
        )


class ReplaceCriteriaRequest(ConstraintSchema):
    criteria: list[CriterionSchema]
