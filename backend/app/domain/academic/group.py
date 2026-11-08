from collections.abc import Iterable
from dataclasses import dataclass, field

from app.domain.academic.errors import SubgroupNameTaken, SubgroupsExceedGroup
from app.domain.academic.names import check_student_count, clean_name, name_key
from app.domain.shared.errors import NotFound
from app.domain.shared.ids import GroupId, ProjectId, SubgroupId

_MISSING_GROUP_NAME = "Укажите название группы"
_MISSING_SUBGROUP_NAME = "Укажите название подгруппы"


@dataclass(frozen=True, kw_only=True)
class Subgroup:
    """Часть группы со своим числом студентов (F_Data_11)."""

    id: SubgroupId
    name: str
    student_count: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "name", clean_name(self.name, field="name", missing=_MISSING_SUBGROUP_NAME)
        )
        check_student_count(self.student_count)


@dataclass(kw_only=True)
class StudentGroup:
    """Учебная группа и её подгруппы (F_Data_10–13).

    Названия подгрупп не повторяются внутри группы, а студентов в них в сумме не больше,
    чем в группе (F_Data_12). Одна подгруппа допустима: противоречие найдёт проверка
    перед расчётом (F_Valid_3).
    """

    id: GroupId
    project_id: ProjectId
    name: str
    student_count: int
    subgroups: tuple[Subgroup, ...] = field(default=())

    def __post_init__(self) -> None:
        self.rename(self.name)
        check_student_count(self.student_count)
        self._replace_subgroups(self.subgroups, self.student_count)

    def rename(self, name: str) -> None:
        self.name = clean_name(name, field="name", missing=_MISSING_GROUP_NAME)

    def change_student_count(self, student_count: int) -> None:
        check_student_count(student_count)
        self._replace_subgroups(self.subgroups, student_count)
        self.student_count = student_count

    def add_subgroup(self, subgroup: Subgroup) -> None:
        self._replace_subgroups((*self.subgroups, subgroup), self.student_count)

    def change_subgroup(self, subgroup: Subgroup) -> None:
        """Заменяет подгруппу с тем же id."""
        self._subgroup(subgroup.id)
        self._replace_subgroups(
            (subgroup if old.id == subgroup.id else old for old in self.subgroups),
            self.student_count,
        )

    def remove_subgroup(self, subgroup_id: SubgroupId) -> None:
        self._subgroup(subgroup_id)
        self.subgroups = tuple(old for old in self.subgroups if old.id != subgroup_id)

    def _subgroup(self, subgroup_id: SubgroupId) -> Subgroup:
        for subgroup in self.subgroups:
            if subgroup.id == subgroup_id:
                return subgroup
        raise NotFound("Подгруппа не найдена", subgroup_id=str(subgroup_id))

    def _replace_subgroups(self, subgroups: Iterable[Subgroup], student_count: int) -> None:
        ordered = tuple(sorted(subgroups, key=lambda subgroup: name_key(subgroup.name)))
        if len({subgroup.id for subgroup in ordered}) != len(ordered):
            raise ValueError("Две подгруппы с одним id")  # ошибка в коде, а не во вводе
        keys = [name_key(subgroup.name) for subgroup in ordered]
        if len(set(keys)) != len(keys):
            raise SubgroupNameTaken("В группе уже есть подгруппа с таким названием", field="name")
        in_subgroups = sum(subgroup.student_count for subgroup in ordered)
        if in_subgroups > student_count:  # F_Data_12
            raise SubgroupsExceedGroup(
                f"В подгруппах {in_subgroups} студентов, а в группе {student_count}",
                field="student_count",
                group_student_count=student_count,
                subgroups_student_count=in_subgroups,
            )
        self.subgroups = ordered
