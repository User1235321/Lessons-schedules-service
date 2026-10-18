from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.projects.project import Project
from app.domain.projects.settings import (
    DurationMode,
    DurationModeKind,
    ProjectSettings,
    StudyCycle,
    TimeMode,
    TimeModeKind,
)
from app.domain.shared.errors import InvalidValue
from app.domain.shared.ids import ProjectId, UserId
from app.domain.shared.week import Weekday

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=1)


def create_project(name: str = "Осенний семестр") -> Project:
    return Project.create(
        project_id=ProjectId(uuid4()), owner_id=UserId(uuid4()), name=name, now=NOW
    )


def test_new_project_gets_default_settings() -> None:
    project = create_project()

    working_days = (
        Weekday.MONDAY,
        Weekday.TUESDAY,
        Weekday.WEDNESDAY,
        Weekday.THURSDAY,
        Weekday.FRIDAY,
        Weekday.SATURDAY,
    )
    assert project.settings.cycle == StudyCycle(working_days, working_days)
    assert project.settings.time_mode == TimeMode.hour_start()
    assert project.settings.duration_mode == DurationMode.uniform(100)
    assert project.created_at == project.updated_at == NOW


def test_project_name_is_trimmed() -> None:
    assert create_project("  Осенний семестр  ").name == "Осенний семестр"


@pytest.mark.parametrize("name", ["", "   ", "x" * 201])
def test_invalid_project_name_is_rejected(name: str) -> None:
    with pytest.raises(InvalidValue) as error:
        create_project(name)

    assert error.value.field == "name"


def test_rename_changes_name_and_update_time() -> None:
    project = create_project()

    project.rename("Весенний семестр", LATER)

    assert project.name == "Весенний семестр"
    assert project.updated_at == LATER


def test_rename_to_blank_name_keeps_project_unchanged() -> None:
    project = create_project()

    with pytest.raises(InvalidValue):
        project.rename("  ", LATER)

    assert project.name == "Осенний семестр"
    assert project.updated_at == NOW


def test_change_settings_changes_update_time() -> None:
    project = create_project()
    settings = ProjectSettings(
        cycle=StudyCycle((Weekday.MONDAY,), ()),
        time_mode=TimeMode.step(30),
        duration_mode=DurationMode.individual(),
    )

    project.change_settings(settings, LATER)

    assert project.settings == settings
    assert project.updated_at == LATER


def test_cycle_keeps_days_in_week_order_without_repeats() -> None:
    cycle = StudyCycle(
        odd_week_days=(Weekday.FRIDAY, Weekday.MONDAY, Weekday.FRIDAY),
        even_week_days=(),
    )

    assert cycle.odd_week_days == (Weekday.MONDAY, Weekday.FRIDAY)
    assert cycle.even_week_days == ()  # противоречие, а не ошибка ввода (F_Valid_3)


@pytest.mark.parametrize("step", [None, 0, -15])
def test_step_mode_requires_positive_step(step: int | None) -> None:
    with pytest.raises(InvalidValue) as error:
        TimeMode(TimeModeKind.STEP, step)

    assert error.value.field == "step_minutes"


def test_hour_start_mode_rejects_step() -> None:
    with pytest.raises(InvalidValue) as error:
        TimeMode(TimeModeKind.HOUR_START, 30)

    assert error.value.field == "step_minutes"


@pytest.mark.parametrize("minutes", [None, 0, -90])
def test_uniform_mode_requires_positive_duration(minutes: int | None) -> None:
    with pytest.raises(InvalidValue) as error:
        DurationMode(DurationModeKind.UNIFORM, minutes)

    assert error.value.field == "duration_minutes"


def test_individual_mode_rejects_duration() -> None:
    with pytest.raises(InvalidValue) as error:
        DurationMode(DurationModeKind.INDIVIDUAL, 90)

    assert error.value.field == "duration_minutes"
