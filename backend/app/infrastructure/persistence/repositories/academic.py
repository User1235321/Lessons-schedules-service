from collections.abc import Iterable, Iterator
from contextlib import contextmanager

from sqlalchemy import ColumnElement, Select, and_, delete, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.domain.academic.errors import (
    GroupInUse,
    GroupNameTaken,
    RoomNameTaken,
    StreamInUse,
    StreamNameTaken,
    SubgroupInUse,
    SubgroupNameTaken,
    SubjectInUse,
    SubjectNameTaken,
)
from app.domain.academic.group import StudentGroup
from app.domain.academic.room import Room
from app.domain.academic.stream import Stream
from app.domain.academic.subject import Subject
from app.domain.academic.teacher import Teacher
from app.domain.academic.workload import Workload
from app.domain.shared.errors import DomainError, InvalidValue, NotFound
from app.domain.shared.ids import (
    GroupId,
    ProjectId,
    RoomId,
    StreamId,
    SubgroupId,
    SubjectId,
    TeacherId,
    WorkloadId,
)
from app.infrastructure.persistence.errors import violated_constraint
from app.infrastructure.persistence.mappers.academic import (
    capability_rows,
    group_to_domain,
    interval_rows,
    room_to_domain,
    stream_to_domain,
    subgroup_row,
    subject_to_domain,
    subject_to_row,
    teacher_to_domain,
    workload_to_domain,
    workload_values,
)
from app.infrastructure.persistence.models import (
    RoomAvailabilityRow,
    RoomCapabilityRow,
    RoomRow,
    StreamGroupRow,
    StreamRow,
    StudentGroupRow,
    SubgroupRow,
    SubjectRow,
    TeacherAvailabilityRow,
    TeacherCapabilityRow,
    TeacherPreferenceRow,
    TeacherRow,
    WorkloadRow,
)


def _domain_error(error: IntegrityError) -> DomainError | None:
    """Нарушение ограничения базы, которое пользователь может исправить сам."""
    match violated_constraint(error):
        case "uq_subjects_project_id_name":
            return SubjectNameTaken("В проекте уже есть дисциплина с таким названием", field="name")
        case "uq_student_groups_project_id_name":
            return GroupNameTaken("В проекте уже есть группа с таким названием", field="name")
        case "uq_subgroups_group_id_name":
            return SubgroupNameTaken("В группе уже есть подгруппа с таким названием", field="name")
        case "uq_rooms_project_id_name":
            return RoomNameTaken("В проекте уже есть аудитория с таким названием", field="name")
        case "uq_student_streams_project_id_name":
            return StreamNameTaken("В проекте уже есть поток с таким названием", field="name")
        case "fk_teacher_capabilities_subject" | "fk_room_capabilities_subject":
            return InvalidValue("Такой дисциплины нет в проекте", field="capabilities")
        case "fk_stream_groups_group":
            return InvalidValue("Такой группы нет в проекте", field="group_ids")
        case "fk_workloads_subject":
            return InvalidValue("Такой дисциплины нет в проекте", field="subject_id")
        case "fk_workloads_group" | "fk_workloads_subgroup" | "fk_workloads_stream":
            return InvalidValue("Такой цели нет в проекте", field="target.id")
    return None


@contextmanager
def _translated() -> Iterator[None]:
    """Переводит нарушения ограничений базы в ошибки предметной области."""
    try:
        yield
    except IntegrityError as error:
        if domain_error := _domain_error(error):
            raise domain_error from error
        raise


# Ссылки, которые не дают удалить данные. Их проверка идёт до удаления, чтобы назвать,
# кто ссылается. Внешний ключ ловит ссылку, появившуюся уже после проверки.
_SUBJECT_REFERENCES = {
    "fk_teacher_capabilities_subject",
    "fk_room_capabilities_subject",
    "fk_workloads_subject",
}
_GROUP_REFERENCES = {"fk_stream_groups_group", "fk_workloads_group", "fk_workloads_subgroup"}


def _workloads_where(session: Session, *conditions: ColumnElement[bool]) -> list[dict[str, str]]:
    ids = session.scalars(select(WorkloadRow.id).where(*conditions).order_by(WorkloadRow.id))
    return [{"id": str(workload_id)} for workload_id in ids]


def _named(rows: Iterable[tuple[object, str]], name: str) -> list[dict[str, str]]:
    return [{"id": str(row_id), name: value} for row_id, value in rows]


def _subject_in_use(
    teachers: list[dict[str, str]], rooms: list[dict[str, str]], workloads: list[dict[str, str]]
) -> SubjectInUse:
    return SubjectInUse(
        "Дисциплина используется в данных проекта",
        teachers=teachers,
        rooms=rooms,
        workloads=workloads,
    )


def _group_in_use(streams: list[dict[str, str]], workloads: list[dict[str, str]]) -> GroupInUse:
    return GroupInUse(
        "Группа используется в потоках или нагрузке", streams=streams, workloads=workloads
    )


class SqlSubjectRepository:
    """Реализует SubjectRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, subject: Subject) -> None:
        self._session.add(subject_to_row(subject))
        with _translated():
            # Сразу, а не при commit: одинаковые названия ловит только уникальный индекс
            self._session.flush()

    def get(self, project_id: ProjectId, subject_id: SubjectId) -> Subject | None:
        row = self._session.scalar(
            select(SubjectRow).where(
                SubjectRow.project_id == project_id, SubjectRow.id == subject_id
            )
        )
        return subject_to_domain(row) if row else None

    def list_in_project(self, project_id: ProjectId) -> list[Subject]:
        rows = self._session.scalars(
            select(SubjectRow)
            .where(SubjectRow.project_id == project_id)
            .order_by(func.lower(SubjectRow.name), SubjectRow.id)
        )
        return [subject_to_domain(row) for row in rows]

    def save(self, subject: Subject) -> None:
        with _translated():
            updated = self._session.scalar(
                update(SubjectRow)
                .where(SubjectRow.project_id == subject.project_id, SubjectRow.id == subject.id)
                .values(name=subject.name)
                .returning(SubjectRow.id)
            )
        if updated is None:
            raise NotFound("Дисциплина не найдена", subject_id=str(subject.id))

    def delete(self, project_id: ProjectId, subject_id: SubjectId) -> None:
        teachers = self._session.execute(
            select(TeacherRow.id, TeacherRow.full_name)
            .join(
                TeacherCapabilityRow,
                and_(
                    TeacherCapabilityRow.project_id == TeacherRow.project_id,
                    TeacherCapabilityRow.teacher_id == TeacherRow.id,
                ),
            )
            .where(
                TeacherCapabilityRow.project_id == project_id,
                TeacherCapabilityRow.subject_id == subject_id,
            )
            .distinct()
            .order_by(TeacherRow.full_name, TeacherRow.id)
        ).all()
        rooms = self._session.execute(
            select(RoomRow.id, RoomRow.name)
            .join(
                RoomCapabilityRow,
                and_(
                    RoomCapabilityRow.project_id == RoomRow.project_id,
                    RoomCapabilityRow.room_id == RoomRow.id,
                ),
            )
            .where(
                RoomCapabilityRow.project_id == project_id,
                RoomCapabilityRow.subject_id == subject_id,
            )
            .distinct()
            .order_by(RoomRow.name, RoomRow.id)
        ).all()
        workloads = _workloads_where(
            self._session,
            WorkloadRow.project_id == project_id,
            WorkloadRow.subject_id == subject_id,
        )
        if teachers or rooms or workloads:
            raise _subject_in_use(_named(teachers, "full_name"), _named(rooms, "name"), workloads)
        try:
            deleted = self._session.scalar(
                delete(SubjectRow)
                .where(SubjectRow.project_id == project_id, SubjectRow.id == subject_id)
                .returning(SubjectRow.id)
            )
        except IntegrityError as error:
            if violated_constraint(error) in _SUBJECT_REFERENCES:
                raise _subject_in_use([], [], []) from error
            raise
        if deleted is None:
            raise NotFound("Дисциплина не найдена", subject_id=str(subject_id))


class SqlTeacherRepository:
    """Реализует TeacherRepository.

    Наборы преподавателя пишутся явными запросами после строки преподавателя: так порядок
    вставки не зависит от того, как SQLAlchemy упорядочит flush.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, teacher: Teacher) -> None:
        self._session.execute(
            insert(TeacherRow).values(
                id=teacher.id, project_id=teacher.project_id, full_name=teacher.full_name
            )
        )
        self._insert_parts(teacher)

    def get(self, project_id: ProjectId, teacher_id: TeacherId) -> Teacher | None:
        row = self._session.scalar(self._query(project_id).where(TeacherRow.id == teacher_id))
        return teacher_to_domain(row) if row else None

    def get_for_update(self, project_id: ProjectId, teacher_id: TeacherId) -> Teacher | None:
        row = self._session.scalar(
            self._query(project_id).where(TeacherRow.id == teacher_id).with_for_update()
        )
        return teacher_to_domain(row) if row else None

    def list_in_project(self, project_id: ProjectId) -> list[Teacher]:
        rows = self._session.scalars(
            self._query(project_id).order_by(func.lower(TeacherRow.full_name), TeacherRow.id)
        )
        return [teacher_to_domain(row) for row in rows]

    def save(self, teacher: Teacher) -> None:
        # Сначала строка преподавателя: её блокировка выстраивает параллельные сохранения в очередь
        updated = self._session.scalar(
            update(TeacherRow)
            .where(TeacherRow.project_id == teacher.project_id, TeacherRow.id == teacher.id)
            .values(full_name=teacher.full_name)
            .returning(TeacherRow.id)
        )
        if updated is None:
            raise NotFound("Преподаватель не найден", teacher_id=str(teacher.id))
        # У строк наборов нет своей идентичности, поэтому наборы заменяются целиком
        for table in (TeacherCapabilityRow, TeacherAvailabilityRow, TeacherPreferenceRow):
            self._session.execute(delete(table).where(table.teacher_id == teacher.id))
        self._insert_parts(teacher)

    def delete(self, project_id: ProjectId, teacher_id: TeacherId) -> None:
        # Наборы удалит база: внешние ключи объявлены с ON DELETE CASCADE
        deleted = self._session.scalar(
            delete(TeacherRow)
            .where(TeacherRow.project_id == project_id, TeacherRow.id == teacher_id)
            .returning(TeacherRow.id)
        )
        if deleted is None:
            raise NotFound("Преподаватель не найден", teacher_id=str(teacher_id))

    def _query(self, project_id: ProjectId) -> Select[tuple[TeacherRow]]:
        return (
            select(TeacherRow)
            .where(TeacherRow.project_id == project_id)
            .options(
                selectinload(TeacherRow.capabilities),
                selectinload(TeacherRow.availability),
                selectinload(TeacherRow.preferences),
            )
            # Наборы пишутся мимо identity map, поэтому строки всегда читаются заново
            .execution_options(populate_existing=True)
        )

    def _insert_parts(self, teacher: Teacher) -> None:
        with _translated():
            self._session.execute(
                insert(TeacherCapabilityRow),
                capability_rows(
                    teacher.project_id, {"teacher_id": teacher.id}, teacher.capabilities
                ),
            )
        self._session.execute(
            insert(TeacherAvailabilityRow),
            interval_rows({"teacher_id": teacher.id}, teacher.availability),
        )
        if teacher.preferences:
            self._session.execute(
                insert(TeacherPreferenceRow),
                interval_rows({"teacher_id": teacher.id}, teacher.preferences),
            )


class SqlGroupRepository:
    """Реализует GroupRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, group: StudentGroup) -> None:
        with _translated():
            self._session.execute(
                insert(StudentGroupRow).values(
                    id=group.id,
                    project_id=group.project_id,
                    name=group.name,
                    student_count=group.student_count,
                )
            )
            if group.subgroups:
                self._session.execute(
                    insert(SubgroupRow), [subgroup_row(group, sub) for sub in group.subgroups]
                )

    def get(self, project_id: ProjectId, group_id: GroupId) -> StudentGroup | None:
        row = self._session.scalar(self._query(project_id).where(StudentGroupRow.id == group_id))
        return group_to_domain(row) if row else None

    def get_for_update(self, project_id: ProjectId, group_id: GroupId) -> StudentGroup | None:
        row = self._session.scalar(
            self._query(project_id).where(StudentGroupRow.id == group_id).with_for_update()
        )
        return group_to_domain(row) if row else None

    def get_by_subgroup(
        self, project_id: ProjectId, subgroup_id: SubgroupId
    ) -> StudentGroup | None:
        row = self._session.scalar(self._by_subgroup(project_id, subgroup_id))
        return group_to_domain(row) if row else None

    def get_by_subgroup_for_update(
        self, project_id: ProjectId, subgroup_id: SubgroupId
    ) -> StudentGroup | None:
        row = self._session.scalar(self._by_subgroup(project_id, subgroup_id).with_for_update())
        return group_to_domain(row) if row else None

    def list_in_project(self, project_id: ProjectId) -> list[StudentGroup]:
        rows = self._session.scalars(
            self._query(project_id).order_by(func.lower(StudentGroupRow.name), StudentGroupRow.id)
        )
        return [group_to_domain(row) for row in rows]

    def save(self, group: StudentGroup) -> None:
        with _translated():
            updated = self._session.scalar(
                update(StudentGroupRow)
                .where(
                    StudentGroupRow.project_id == group.project_id, StudentGroupRow.id == group.id
                )
                .values(name=group.name, student_count=group.student_count)
                .returning(StudentGroupRow.id)
            )
            if updated is None:
                raise NotFound("Группа не найдена", group_id=str(group.id))
            self._save_subgroups(group)

    def delete(self, project_id: ProjectId, group_id: GroupId) -> None:
        streams = self._session.execute(
            select(StreamRow.id, StreamRow.name)
            .join(
                StreamGroupRow,
                and_(
                    StreamGroupRow.project_id == StreamRow.project_id,
                    StreamGroupRow.stream_id == StreamRow.id,
                ),
            )
            .where(StreamGroupRow.project_id == project_id, StreamGroupRow.group_id == group_id)
            .order_by(StreamRow.name, StreamRow.id)
        ).all()
        # Подгруппы удаляются вместе с группой, поэтому их нагрузка тоже мешает
        subgroups = select(SubgroupRow.id).where(SubgroupRow.group_id == group_id)
        workloads = _workloads_where(
            self._session,
            WorkloadRow.project_id == project_id,
            or_(WorkloadRow.group_id == group_id, WorkloadRow.subgroup_id.in_(subgroups)),
        )
        if streams or workloads:
            raise _group_in_use(_named(streams, "name"), workloads)
        try:
            deleted = self._session.scalar(
                delete(StudentGroupRow)
                .where(StudentGroupRow.project_id == project_id, StudentGroupRow.id == group_id)
                .returning(StudentGroupRow.id)
            )
        except IntegrityError as error:
            if violated_constraint(error) in _GROUP_REFERENCES:
                raise _group_in_use([], []) from error
            raise
        if deleted is None:
            raise NotFound("Группа не найдена", group_id=str(group_id))

    def _query(self, project_id: ProjectId) -> Select[tuple[StudentGroupRow]]:
        return (
            select(StudentGroupRow)
            .where(StudentGroupRow.project_id == project_id)
            .options(selectinload(StudentGroupRow.subgroups))
            .execution_options(populate_existing=True)
        )

    def _by_subgroup(
        self, project_id: ProjectId, subgroup_id: SubgroupId
    ) -> Select[tuple[StudentGroupRow]]:
        group_id = select(SubgroupRow.group_id).where(
            SubgroupRow.project_id == project_id, SubgroupRow.id == subgroup_id
        )
        return self._query(project_id).where(StudentGroupRow.id == group_id.scalar_subquery())

    def _save_subgroups(self, group: StudentGroup) -> None:
        # Подгруппы сохраняются по id, а не заменяются целиком: на них будет ссылаться нагрузка
        stored = set(
            self._session.scalars(select(SubgroupRow.id).where(SubgroupRow.group_id == group.id))
        )
        removed = stored - {subgroup.id for subgroup in group.subgroups}
        if removed:
            workloads = _workloads_where(self._session, WorkloadRow.subgroup_id.in_(removed))
            in_use = SubgroupInUse("Подгруппа используется в нагрузке", workloads=workloads)
            if workloads:
                raise in_use
            try:
                # До вставки новых: освободившееся название можно сразу занять
                self._session.execute(
                    delete(SubgroupRow).where(
                        SubgroupRow.group_id == group.id, SubgroupRow.id.in_(removed)
                    )
                )
            except IntegrityError as error:
                # Тот же ключ при вставке нагрузки значит другое, поэтому ловим здесь
                if violated_constraint(error) == "fk_workloads_subgroup":
                    raise in_use from error
                raise
        for subgroup in group.subgroups:
            if subgroup.id in stored:
                self._session.execute(
                    update(SubgroupRow)
                    .where(SubgroupRow.group_id == group.id, SubgroupRow.id == subgroup.id)
                    .values(name=subgroup.name, student_count=subgroup.student_count)
                )
            else:
                self._session.execute(insert(SubgroupRow).values(subgroup_row(group, subgroup)))


class SqlRoomRepository:
    """Реализует RoomRepository. Устроен как SqlTeacherRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, room: Room) -> None:
        with _translated():
            self._session.execute(
                insert(RoomRow).values(
                    id=room.id,
                    project_id=room.project_id,
                    name=room.name,
                    capacity=room.capacity,
                    type=str(room.type),
                )
            )
        self._insert_parts(room)

    def get(self, project_id: ProjectId, room_id: RoomId) -> Room | None:
        row = self._session.scalar(self._query(project_id).where(RoomRow.id == room_id))
        return room_to_domain(row) if row else None

    def get_for_update(self, project_id: ProjectId, room_id: RoomId) -> Room | None:
        row = self._session.scalar(
            self._query(project_id).where(RoomRow.id == room_id).with_for_update()
        )
        return room_to_domain(row) if row else None

    def list_in_project(self, project_id: ProjectId) -> list[Room]:
        rows = self._session.scalars(
            self._query(project_id).order_by(func.lower(RoomRow.name), RoomRow.id)
        )
        return [room_to_domain(row) for row in rows]

    def save(self, room: Room) -> None:
        with _translated():
            updated = self._session.scalar(
                update(RoomRow)
                .where(RoomRow.project_id == room.project_id, RoomRow.id == room.id)
                .values(name=room.name, capacity=room.capacity, type=str(room.type))
                .returning(RoomRow.id)
            )
        if updated is None:
            raise NotFound("Аудитория не найдена", room_id=str(room.id))
        for table in (RoomCapabilityRow, RoomAvailabilityRow):
            self._session.execute(delete(table).where(table.room_id == room.id))
        self._insert_parts(room)

    def delete(self, project_id: ProjectId, room_id: RoomId) -> None:
        deleted = self._session.scalar(
            delete(RoomRow)
            .where(RoomRow.project_id == project_id, RoomRow.id == room_id)
            .returning(RoomRow.id)
        )
        if deleted is None:
            raise NotFound("Аудитория не найдена", room_id=str(room_id))

    def _query(self, project_id: ProjectId) -> Select[tuple[RoomRow]]:
        return (
            select(RoomRow)
            .where(RoomRow.project_id == project_id)
            .options(selectinload(RoomRow.availability), selectinload(RoomRow.capabilities))
            .execution_options(populate_existing=True)
        )

    def _insert_parts(self, room: Room) -> None:
        owner = {"room_id": room.id}
        self._session.execute(insert(RoomAvailabilityRow), interval_rows(owner, room.availability))
        if room.capabilities:
            with _translated():
                self._session.execute(
                    insert(RoomCapabilityRow),
                    capability_rows(room.project_id, owner, room.capabilities),
                )


class SqlStreamRepository:
    """Реализует StreamRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, stream: Stream) -> None:
        with _translated():
            self._session.execute(
                insert(StreamRow).values(
                    id=stream.id, project_id=stream.project_id, name=stream.name
                )
            )
            self._insert_groups(stream)

    def get(self, project_id: ProjectId, stream_id: StreamId) -> Stream | None:
        row = self._session.scalar(self._query(project_id).where(StreamRow.id == stream_id))
        return stream_to_domain(row) if row else None

    def get_for_update(self, project_id: ProjectId, stream_id: StreamId) -> Stream | None:
        row = self._session.scalar(
            self._query(project_id).where(StreamRow.id == stream_id).with_for_update()
        )
        return stream_to_domain(row) if row else None

    def list_in_project(self, project_id: ProjectId) -> list[Stream]:
        rows = self._session.scalars(
            self._query(project_id).order_by(func.lower(StreamRow.name), StreamRow.id)
        )
        return [stream_to_domain(row) for row in rows]

    def save(self, stream: Stream) -> None:
        with _translated():
            updated = self._session.scalar(
                update(StreamRow)
                .where(StreamRow.project_id == stream.project_id, StreamRow.id == stream.id)
                .values(name=stream.name)
                .returning(StreamRow.id)
            )
            if updated is None:
                raise NotFound("Поток не найден", stream_id=str(stream.id))
            self._session.execute(
                delete(StreamGroupRow).where(StreamGroupRow.stream_id == stream.id)
            )
            self._insert_groups(stream)

    def delete(self, project_id: ProjectId, stream_id: StreamId) -> None:
        workloads = _workloads_where(
            self._session, WorkloadRow.project_id == project_id, WorkloadRow.stream_id == stream_id
        )
        in_use = StreamInUse("Поток используется в нагрузке", workloads=workloads)
        if workloads:
            raise in_use
        try:
            deleted = self._session.scalar(
                delete(StreamRow)
                .where(StreamRow.project_id == project_id, StreamRow.id == stream_id)
                .returning(StreamRow.id)
            )
        except IntegrityError as error:
            if violated_constraint(error) == "fk_workloads_stream":
                raise in_use from error
            raise
        if deleted is None:
            raise NotFound("Поток не найден", stream_id=str(stream_id))

    def _query(self, project_id: ProjectId) -> Select[tuple[StreamRow]]:
        return (
            select(StreamRow)
            .where(StreamRow.project_id == project_id)
            .options(selectinload(StreamRow.groups))
            .execution_options(populate_existing=True)
        )

    def _insert_groups(self, stream: Stream) -> None:
        self._session.execute(
            insert(StreamGroupRow),
            [
                {"project_id": stream.project_id, "stream_id": stream.id, "group_id": group_id}
                for group_id in stream.group_ids
            ],
        )


class SqlWorkloadRepository:
    """Реализует WorkloadRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, workload: Workload) -> None:
        with _translated():
            self._session.execute(
                insert(WorkloadRow).values(
                    id=workload.id, project_id=workload.project_id, **workload_values(workload)
                )
            )

    def get(self, project_id: ProjectId, workload_id: WorkloadId) -> Workload | None:
        row = self._session.scalar(self._query(project_id).where(WorkloadRow.id == workload_id))
        return workload_to_domain(row) if row else None

    def get_for_update(self, project_id: ProjectId, workload_id: WorkloadId) -> Workload | None:
        row = self._session.scalar(
            self._query(project_id).where(WorkloadRow.id == workload_id).with_for_update()
        )
        return workload_to_domain(row) if row else None

    def list_in_project(self, project_id: ProjectId) -> list[Workload]:
        rows = self._session.scalars(
            self._query(project_id)
            .join(
                SubjectRow,
                and_(
                    SubjectRow.project_id == WorkloadRow.project_id,
                    SubjectRow.id == WorkloadRow.subject_id,
                ),
            )
            .order_by(func.lower(SubjectRow.name), WorkloadRow.lesson_type, WorkloadRow.id)
        )
        return [workload_to_domain(row) for row in rows]

    def save(self, workload: Workload) -> None:
        with _translated():
            updated = self._session.scalar(
                update(WorkloadRow)
                .where(WorkloadRow.project_id == workload.project_id, WorkloadRow.id == workload.id)
                .values(workload_values(workload))
                .returning(WorkloadRow.id)
            )
        if updated is None:
            raise NotFound("Нагрузка не найдена", workload_id=str(workload.id))

    def delete(self, project_id: ProjectId, workload_id: WorkloadId) -> None:
        deleted = self._session.scalar(
            delete(WorkloadRow)
            .where(WorkloadRow.project_id == project_id, WorkloadRow.id == workload_id)
            .returning(WorkloadRow.id)
        )
        if deleted is None:
            raise NotFound("Нагрузка не найдена", workload_id=str(workload_id))

    def _query(self, project_id: ProjectId) -> Select[tuple[WorkloadRow]]:
        return (
            select(WorkloadRow)
            .where(WorkloadRow.project_id == project_id)
            .execution_options(populate_existing=True)
        )
