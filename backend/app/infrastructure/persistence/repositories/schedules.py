from collections import defaultdict

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.domain.scheduling.schedule import Schedule
from app.domain.shared.errors import NotFound
from app.domain.shared.ids import JobId, ProjectId, ScheduleId
from app.infrastructure.persistence.mappers.schedules import (
    entry_to_domain,
    entry_to_row,
    schedule_to_domain,
    schedule_to_row,
)
from app.infrastructure.persistence.models.schedules import (
    ScheduleEntryRow,
    ScheduleEntryTeacherRow,
    ScheduleRow,
)


class SqlScheduleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, schedule: Schedule) -> None:
        self._session.add(schedule_to_row(schedule))
        self._session.flush()
        self._add_entries(schedule)

    def get(self, project_id: ProjectId, schedule_id: ScheduleId) -> Schedule | None:
        return self._get(project_id, schedule_id, for_update=False)

    def get_for_update(self, project_id: ProjectId, schedule_id: ScheduleId) -> Schedule | None:
        return self._get(project_id, schedule_id, for_update=True)

    def _get(
        self, project_id: ProjectId, schedule_id: ScheduleId, *, for_update: bool
    ) -> Schedule | None:
        query = select(ScheduleRow).where(
            ScheduleRow.id == schedule_id, ScheduleRow.project_id == project_id
        )
        if for_update:
            query = query.with_for_update()
        row = self._session.scalar(query)
        return self._load(row) if row else None

    def list_for_job(self, project_id: ProjectId, job_id: JobId) -> list[Schedule]:
        rows = self._session.scalars(
            select(ScheduleRow)
            .where(ScheduleRow.project_id == project_id, ScheduleRow.job_id == job_id)
            .order_by(ScheduleRow.result_index)
        ).all()
        return [self._load(row) for row in rows]

    def list_in_project(self, project_id: ProjectId) -> list[Schedule]:
        rows = self._session.scalars(
            select(ScheduleRow)
            .where(ScheduleRow.project_id == project_id)
            .order_by(ScheduleRow.created_at, ScheduleRow.id)
        ).all()
        return [self._load(row) for row in rows]

    def save(self, schedule: Schedule) -> None:
        row = schedule_to_row(schedule)
        updated = self._session.scalar(
            update(ScheduleRow)
            .where(ScheduleRow.id == schedule.id, ScheduleRow.project_id == schedule.project_id)
            .values(criterion_scores=row.criterion_scores)
            .returning(ScheduleRow.id)
        )
        if updated is None:
            raise NotFound("Расписание не найдено", schedule_id=str(schedule.id))
        self._session.execute(
            delete(ScheduleEntryRow).where(ScheduleEntryRow.schedule_id == schedule.id)
        )
        self._add_entries(schedule)

    def _add_entries(self, schedule: Schedule) -> None:
        self._session.add_all(
            entry_to_row(entry, schedule.id, position)
            for position, entry in enumerate(schedule.entries)
        )
        self._session.flush()
        self._session.add_all(
            ScheduleEntryTeacherRow(
                entry_id=entry.id,
                position=position,
                teacher_id=teacher.teacher_id,
                display_name=teacher.display_name,
            )
            for entry in schedule.entries
            for position, teacher in enumerate(entry.teachers)
        )

    def _load(self, row: ScheduleRow) -> Schedule:
        entries = self._session.scalars(
            select(ScheduleEntryRow)
            .where(ScheduleEntryRow.schedule_id == row.id)
            .order_by(ScheduleEntryRow.position)
        ).all()
        teachers_by_entry = defaultdict(list)
        if entries:
            teachers = self._session.scalars(
                select(ScheduleEntryTeacherRow)
                .where(ScheduleEntryTeacherRow.entry_id.in_([entry.id for entry in entries]))
                .order_by(ScheduleEntryTeacherRow.position)
            )
            for teacher in teachers:
                teachers_by_entry[teacher.entry_id].append(teacher)
        return schedule_to_domain(
            row, tuple(entry_to_domain(entry, teachers_by_entry[entry.id]) for entry in entries)
        )
