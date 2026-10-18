from dataclasses import dataclass
from enum import StrEnum

from app.domain.shared.errors import InvalidValue
from app.domain.shared.week import Weekday, ordered_weekdays

MONDAY_TO_SATURDAY = (
    Weekday.MONDAY,
    Weekday.TUESDAY,
    Weekday.WEDNESDAY,
    Weekday.THURSDAY,
    Weekday.FRIDAY,
    Weekday.SATURDAY,
)
DEFAULT_DURATION_MINUTES = 100  # одна пара в Политехе: 1 час 40 минут


@dataclass(frozen=True)
class StudyCycle:
    """Учебные дни нечётной и чётной недели двухнедельного цикла (F_Data_1).

    Пустой набор допустим: это противоречие, а не ошибка ввода, и его найдёт
    проверка перед расчётом (F_Valid_3).
    """

    odd_week_days: tuple[Weekday, ...]
    even_week_days: tuple[Weekday, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "odd_week_days", ordered_weekdays(self.odd_week_days))
        object.__setattr__(self, "even_week_days", ordered_weekdays(self.even_week_days))


class TimeModeKind(StrEnum):
    HOUR_START = "HOUR_START"  # занятия начинаются только в начале часа
    STEP = "STEP"  # занятия начинаются с заданным минимальным шагом


@dataclass(frozen=True)
class TimeMode:
    """Режим начала занятий (F_Data_2)."""

    kind: TimeModeKind
    step_minutes: int | None = None

    def __post_init__(self) -> None:
        _check_value_matches_kind(
            self.step_minutes,
            required=self.kind is TimeModeKind.STEP,
            field="step_minutes",
            what="шаг",
            kind=TimeModeKind.STEP,
        )

    @classmethod
    def hour_start(cls) -> "TimeMode":
        return cls(TimeModeKind.HOUR_START)

    @classmethod
    def step(cls, minutes: int) -> "TimeMode":
        return cls(TimeModeKind.STEP, minutes)


class DurationModeKind(StrEnum):
    UNIFORM = "UNIFORM"  # одна длительность у всех занятий проекта
    INDIVIDUAL = "INDIVIDUAL"  # длительность задаётся у каждого элемента нагрузки


@dataclass(frozen=True)
class DurationMode:
    """Режим длительности занятий (F_Data_3)."""

    kind: DurationModeKind
    duration_minutes: int | None = None

    def __post_init__(self) -> None:
        _check_value_matches_kind(
            self.duration_minutes,
            required=self.kind is DurationModeKind.UNIFORM,
            field="duration_minutes",
            what="длительность",
            kind=DurationModeKind.UNIFORM,
        )

    @classmethod
    def uniform(cls, minutes: int) -> "DurationMode":
        return cls(DurationModeKind.UNIFORM, minutes)

    @classmethod
    def individual(cls) -> "DurationMode":
        return cls(DurationModeKind.INDIVIDUAL)


@dataclass(frozen=True)
class ProjectSettings:
    """Настройки времени проекта (HLD 9.3)."""

    cycle: StudyCycle
    time_mode: TimeMode
    duration_mode: DurationMode

    @classmethod
    def default(cls) -> "ProjectSettings":
        # При создании проекта обязательно только имя (F_Project_1), остальное — отсюда.
        return cls(
            cycle=StudyCycle(odd_week_days=MONDAY_TO_SATURDAY, even_week_days=MONDAY_TO_SATURDAY),
            time_mode=TimeMode.hour_start(),
            duration_mode=DurationMode.uniform(DEFAULT_DURATION_MINUTES),
        )


def _check_value_matches_kind(
    value: int | None, *, required: bool, field: str, what: str, kind: StrEnum
) -> None:
    if not required:
        if value is not None:
            raise InvalidValue(f"{what.capitalize()} задаётся только в режиме {kind}", field=field)
        return
    if value is None:
        raise InvalidValue(f"В режиме {kind} нужно указать {what}", field=field)
    if value <= 0:  # F_Valid_1
        raise InvalidValue("Нужно положительное число минут", field=field)
