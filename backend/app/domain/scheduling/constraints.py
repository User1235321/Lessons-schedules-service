from dataclasses import dataclass
from datetime import time
from enum import StrEnum
from uuid import UUID

from app.domain.scheduling.resources import CycleWeek, WeeklyWindow
from app.domain.shared.errors import InvalidValue
from app.domain.shared.week import Weekday


class ConstraintKind(StrEnum):
    MIN_START_TIME = "MIN_START_TIME"
    MAX_END_TIME = "MAX_END_TIME"
    ALLOWED_DAYS = "ALLOWED_DAYS"
    EVERY_WEEK = "EVERY_WEEK"
    CONSECUTIVE = "CONSECUTIVE"
    NOT_CONSECUTIVE = "NOT_CONSECUTIVE"
    MIN_GAP = "MIN_GAP"
    BEFORE = "BEFORE"
    FIXED_DAY = "FIXED_DAY"
    TIME_RANGE = "TIME_RANGE"


class ConstraintScopeKind(StrEnum):
    PROJECT = "PROJECT"
    GROUP = "GROUP"
    SUBGROUP = "SUBGROUP"
    STREAM = "STREAM"
    WORKLOAD = "WORKLOAD"


@dataclass(frozen=True)
class ConstraintScope:
    kind: ConstraintScopeKind
    resource_id: UUID | None = None

    def __post_init__(self) -> None:
        if (self.kind is ConstraintScopeKind.PROJECT) == (self.resource_id is not None):
            raise InvalidValue(
                "Укажите ресурс для выбранной области ограничения", field="resource_id"
            )


@dataclass(frozen=True)
class ClockTimeParameters:
    value: time


@dataclass(frozen=True)
class AllowedDaysParameters:
    days: tuple[Weekday, ...]


@dataclass(frozen=True)
class EveryWeekParameters:
    pass


@dataclass(frozen=True)
class RelatedWorkloadParameters:
    workload_id: UUID


@dataclass(frozen=True)
class MinimumGapParameters:
    workload_id: UUID
    minutes: int

    def __post_init__(self) -> None:
        if self.minutes <= 0:
            raise InvalidValue("Интервал должен быть положительным", field="minutes")


@dataclass(frozen=True)
class FixedDayParameters:
    day: Weekday
    week: CycleWeek = "ANY"


@dataclass(frozen=True)
class TimeRangeParameters:
    windows: tuple[WeeklyWindow, ...]


ConstraintParameters = (
    ClockTimeParameters
    | AllowedDaysParameters
    | EveryWeekParameters
    | RelatedWorkloadParameters
    | MinimumGapParameters
    | FixedDayParameters
    | TimeRangeParameters
)

_PARAMETER_TYPES: dict[ConstraintKind, type[object]] = {
    ConstraintKind.MIN_START_TIME: ClockTimeParameters,
    ConstraintKind.MAX_END_TIME: ClockTimeParameters,
    ConstraintKind.ALLOWED_DAYS: AllowedDaysParameters,
    ConstraintKind.EVERY_WEEK: EveryWeekParameters,
    ConstraintKind.CONSECUTIVE: RelatedWorkloadParameters,
    ConstraintKind.NOT_CONSECUTIVE: RelatedWorkloadParameters,
    ConstraintKind.MIN_GAP: MinimumGapParameters,
    ConstraintKind.BEFORE: RelatedWorkloadParameters,
    ConstraintKind.FIXED_DAY: FixedDayParameters,
    ConstraintKind.TIME_RANGE: TimeRangeParameters,
}


@dataclass(frozen=True)
class ExtraConstraintSnapshot:
    id: UUID
    kind: ConstraintKind
    scope: ConstraintScope
    parameters: ConstraintParameters

    def __post_init__(self) -> None:
        if not isinstance(self.parameters, _PARAMETER_TYPES[self.kind]):
            raise InvalidValue("Параметры не соответствуют типу ограничения", field="parameters")
