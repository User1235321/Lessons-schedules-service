from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from app.domain.scheduling.job import JobProgress
from app.domain.scheduling.schedule import CriterionScore, ScheduleEntry
from app.domain.shared.errors import InvalidValue


class SolverControl(Protocol):
    def report_progress(self, progress: JobProgress) -> None: ...

    def is_cancel_requested(self) -> bool: ...


class SolverStatus(StrEnum):
    SOLVED = "SOLVED"
    INFEASIBLE = "INFEASIBLE"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class ScheduleVariant:
    entries: tuple[ScheduleEntry, ...]
    criterion_scores: tuple[CriterionScore, ...]


@dataclass(frozen=True)
class SolverDiagnostic:
    message: str
    workload_ids: tuple[UUID, ...] = ()
    constraint_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True)
class SolverResult:
    status: SolverStatus
    variants: tuple[ScheduleVariant, ...] = ()
    diagnostics: tuple[SolverDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        if (self.status is SolverStatus.SOLVED) != bool(self.variants):
            raise InvalidValue("Варианты допустимы и обязательны только для SOLVED", field="variants")
