from datetime import time
from uuid import uuid4

import pytest

from app.domain.academic.capability import Capability
from app.domain.academic.errors import SubgroupNameTaken, SubgroupsExceedGroup
from app.domain.academic.group import StudentGroup, Subgroup
from app.domain.academic.lesson_type import LessonType
from app.domain.academic.subject import Subject
from app.domain.academic.teacher import Teacher
from app.domain.shared.errors import InvalidValue, NotFound
from app.domain.shared.ids import GroupId, ProjectId, SubgroupId, SubjectId, TeacherId
from app.domain.shared.week import Week, Weekday, WeeklyInterval, ordered_intervals

PROJECT = ProjectId(uuid4())
MATH = SubjectId(uuid4())


def interval(
    week: Week = Week.ODD, day: Weekday = Weekday.MONDAY, start: int = 9, end: int = 18
) -> WeeklyInterval:
    return WeeklyInterval(week, day, time(start), time(end))


def a_teacher(**overrides: object) -> Teacher:
    values: dict[str, object] = {
        "id": TeacherId(uuid4()),
        "project_id": PROJECT,
        "full_name": "Петрова Анна Викторовна",
        "capabilities": (Capability(MATH, LessonType.LECTURE),),
        "availability": (interval(),),
    }
    return Teacher(**(values | overrides))


def a_subgroup(name: str, student_count: int) -> Subgroup:
    return Subgroup(id=SubgroupId(uuid4()), name=name, student_count=student_count)


def a_group(student_count: int = 24, *subgroups: Subgroup) -> StudentGroup:
    return StudentGroup(
        id=GroupId(uuid4()),
        project_id=PROJECT,
        name="301",
        student_count=student_count,
        subgroups=subgroups,
    )


@pytest.mark.parametrize(("start", "end"), [(10, 10), (12, 9)])
def test_interval_must_end_after_start(start: int, end: int) -> None:  # F_Valid_1
    with pytest.raises(InvalidValue) as error:
        interval(start=start, end=end)

    assert error.value.field == "end"


def test_intervals_lose_exact_repeats_and_get_ordered_but_overlaps_stay() -> None:  # F_Valid_3
    even = interval(Week.EVEN, Weekday.MONDAY)
    odd_tuesday = interval(Week.ODD, Weekday.TUESDAY)
    odd_monday, overlapping = interval(start=9, end=12), interval(start=11, end=14)

    ordered = ordered_intervals([even, odd_tuesday, overlapping, odd_monday, even])

    assert ordered == (odd_monday, overlapping, odd_tuesday, even)


@pytest.mark.parametrize("name", ["", "   ", "x" * 201])
def test_subject_needs_a_sensible_name(name: str) -> None:
    with pytest.raises(InvalidValue) as error:
        Subject(id=SubjectId(uuid4()), project_id=PROJECT, name=name)

    assert error.value.field == "name"


def test_teacher_needs_name_capability_and_availability() -> None:  # F_Data_4
    for field, overrides in (
        ("full_name", {"full_name": " "}),
        ("capabilities", {"capabilities": ()}),
        ("availability", {"availability": ()}),
    ):
        with pytest.raises(InvalidValue) as error:
            a_teacher(**overrides)
        assert error.value.field == field


def test_teacher_preferences_are_optional_and_repeats_are_dropped() -> None:
    lecture = Capability(MATH, LessonType.LECTURE)

    teacher = a_teacher(
        capabilities=(lecture, lecture, Capability(MATH, LessonType.LAB)),
        availability=(interval(), interval()),
    )

    assert teacher.preferences == ()
    assert teacher.capabilities == (lecture, Capability(MATH, LessonType.LAB))
    assert teacher.availability == (interval(),)


def test_group_and_subgroups_need_positive_student_count() -> None:  # F_Valid_1
    with pytest.raises(InvalidValue) as error:
        a_group(0)
    assert error.value.field == "student_count"

    with pytest.raises(InvalidValue):
        a_subgroup("301-1", 0)


def test_one_subgroup_is_allowed() -> None:
    group = a_group(24, a_subgroup("301-1", 12))

    assert [subgroup.name for subgroup in group.subgroups] == ["301-1"]


def test_subgroups_cannot_hold_more_students_than_group() -> None:  # F_Data_12
    group = a_group(24, a_subgroup("301-1", 12))

    with pytest.raises(SubgroupsExceedGroup) as error:
        group.add_subgroup(a_subgroup("301-2", 13))

    assert error.value.details == {
        "field": "student_count",
        "group_student_count": 24,
        "subgroups_student_count": 25,
    }
    assert len(group.subgroups) == 1


def test_group_cannot_shrink_below_its_subgroups() -> None:  # F_Data_12
    group = a_group(24, a_subgroup("301-1", 12), a_subgroup("301-2", 12))

    with pytest.raises(SubgroupsExceedGroup):
        group.change_student_count(23)

    assert group.student_count == 24


def test_subgroup_names_are_unique_in_group_regardless_of_case() -> None:
    group = a_group(24, a_subgroup("301-a", 12))

    with pytest.raises(SubgroupNameTaken):
        group.add_subgroup(a_subgroup("301-A", 6))


def test_subgroup_is_changed_and_removed_by_id() -> None:
    first, second = a_subgroup("301-1", 12), a_subgroup("301-2", 12)
    group = a_group(24, first, second)

    group.change_subgroup(Subgroup(id=first.id, name="301-1а", student_count=10))
    group.remove_subgroup(second.id)

    assert group.subgroups == (Subgroup(id=first.id, name="301-1а", student_count=10),)
    with pytest.raises(NotFound):
        group.remove_subgroup(second.id)
