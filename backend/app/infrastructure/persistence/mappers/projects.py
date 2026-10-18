from app.domain.projects.project import Project
from app.domain.projects.settings import (
    DurationMode,
    DurationModeKind,
    ProjectSettings,
    StudyCycle,
    TimeMode,
    TimeModeKind,
)
from app.domain.shared.ids import ProjectId, UserId
from app.domain.shared.week import Weekday
from app.infrastructure.persistence.models import ProjectRow


def fill_project_row(row: ProjectRow, project: Project) -> ProjectRow:
    settings = project.settings
    row.owner_id = project.owner_id
    row.name = project.name
    row.odd_week_days = [str(day) for day in settings.cycle.odd_week_days]
    row.even_week_days = [str(day) for day in settings.cycle.even_week_days]
    row.time_mode = str(settings.time_mode.kind)
    row.time_step_minutes = settings.time_mode.step_minutes
    row.duration_mode = str(settings.duration_mode.kind)
    row.duration_minutes = settings.duration_mode.duration_minutes
    row.created_at = project.created_at
    row.updated_at = project.updated_at
    return row


def project_to_row(project: Project) -> ProjectRow:
    return fill_project_row(ProjectRow(id=project.id), project)


def project_to_domain(row: ProjectRow) -> Project:
    return Project(
        id=ProjectId(row.id),
        owner_id=UserId(row.owner_id),
        name=row.name,
        settings=ProjectSettings(
            cycle=StudyCycle(
                odd_week_days=tuple(Weekday(day) for day in row.odd_week_days),
                even_week_days=tuple(Weekday(day) for day in row.even_week_days),
            ),
            time_mode=TimeMode(TimeModeKind(row.time_mode), row.time_step_minutes),
            duration_mode=DurationMode(DurationModeKind(row.duration_mode), row.duration_minutes),
        ),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
