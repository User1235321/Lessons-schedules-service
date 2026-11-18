from dataclasses import replace
from datetime import time
from uuid import uuid4

import pytest

from app.domain.academic.capability import Capability
from app.domain.academic.lesson_type import LessonType
from app.domain.academic.room import Room, RoomType
from app.domain.academic.stream import Stream
from app.domain.academic.workload import LessonFormat, TargetType, Workload, WorkloadTarget
from app.domain.shared.errors import InvalidValue
from app.domain.shared.ids import GroupId, ProjectId, RoomId, StreamId, SubjectId, WorkloadId
from app.domain.shared.week import Week, Weekday, WeeklyInterval

PROJECT = ProjectId(uuid4())
PHYSICS = SubjectId(uuid4())
ALL_DAY = WeeklyInterval(Week.ANY, Weekday.MONDAY, time(9), time(18))
PHYSICS_LAB = Capability(PHYSICS, LessonType.LAB)


def a_room(**overrides: object) -> Room:
    values: dict[str, object] = {
        "id": RoomId(uuid4()),
        "project_id": PROJECT,
        "name": "215",
        "capacity": 30,
        "type": RoomType.LABORATORY,
        "availability": (ALL_DAY,),
        "capabilities": (PHYSICS_LAB,),
    }
    return Room(**(values | overrides))


def a_workload(**overrides: object) -> Workload:
    values: dict[str, object] = {
        "id": WorkloadId(uuid4()),
        "project_id": PROJECT,
        "target": WorkloadTarget(TargetType.GROUP, uuid4()),
        "subject_id": PHYSICS,
        "lesson_type": LessonType.LAB,
        "format": LessonFormat.ONSITE,
        "occurrences_per_cycle": 2,
    }
    return Workload(**(values | overrides))


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"name": " "}, "name"),
        ({"capacity": 0}, "capacity"),
        ({"availability": ()}, "availability"),
        ({"type": RoomType.LECTURE}, "capabilities"),
        ({"type": RoomType.PRACTICE_UNIVERSAL}, "capabilities"),
    ],
)
def test_invalid_room_names_the_field(overrides: dict[str, object], field: str) -> None:
    # F_Data_7, F_Data_9, F_Valid_1
    with pytest.raises(InvalidValue) as error:
        a_room(**overrides)

    assert error.value.field == field


def test_specialized_room_may_have_no_capabilities() -> None:
    room = a_room(type=RoomType.PRACTICE_SPECIALIZED, capabilities=())

    assert room.capabilities == ()


def test_room_type_changes_together_with_capabilities() -> None:
    room = a_room()

    with pytest.raises(InvalidValue):
        room.change_type(RoomType.LECTURE, room.capabilities)
    assert room.type is RoomType.LABORATORY

    room.change_type(RoomType.LECTURE, ())
    assert (room.type, room.capabilities) == (RoomType.LECTURE, ())


def test_stream_needs_a_group_and_drops_repeats() -> None:  # F_Data_14
    group = GroupId(uuid4())

    with pytest.raises(InvalidValue) as error:
        Stream(id=StreamId(uuid4()), project_id=PROJECT, name="301 + 302", group_ids=())
    stream = Stream(id=StreamId(uuid4()), project_id=PROJECT, name="301", group_ids=(group, group))

    assert error.value.field == "group_ids"
    assert stream.group_ids == (group,)


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"occurrences_per_cycle": 0}, "occurrences_per_cycle"),
        ({"duration_minutes": 0}, "duration_minutes"),
        ({"required_teacher_count": 0}, "required_teacher_count"),
        (
            {"lesson_type": LessonType.LECTURE, "required_teacher_count": 2},
            "required_teacher_count",
        ),
        (
            {"lesson_type": LessonType.PRACTICE, "required_teacher_count": 2},
            "required_teacher_count",
        ),
    ],
)
def test_invalid_workload_names_the_field(overrides: dict[str, object], field: str) -> None:
    # F_Data_16, F_Valid_1, HLD 9.8
    with pytest.raises(InvalidValue) as error:
        a_workload(**overrides)

    assert error.value.field == field


def test_lab_may_need_several_teachers_and_duration_is_optional() -> None:
    workload = a_workload(required_teacher_count=2)

    assert (workload.duration_minutes, workload.required_teacher_count) == (None, 2)


def test_replaced_workload_is_checked_again() -> None:
    with pytest.raises(InvalidValue):
        replace(a_workload(), occurrences_per_cycle=-1)
