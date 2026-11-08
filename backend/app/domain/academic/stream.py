from collections.abc import Iterable
from dataclasses import dataclass

from app.domain.academic.names import clean_name
from app.domain.shared.errors import InvalidValue
from app.domain.shared.ids import GroupId, ProjectId, StreamId

_MISSING_NAME = "Укажите название потока"


@dataclass(kw_only=True)
class Stream:
    """Поток: группы, которые слушают занятия вместе (F_Data_14).

    Потоки собирает только пользователь (F_Data_15). Нужна хотя бы одна группа;
    поток из одной группы допустим.
    """

    id: StreamId
    project_id: ProjectId
    name: str
    group_ids: tuple[GroupId, ...]

    def __post_init__(self) -> None:
        self.rename(self.name)
        self.change_groups(self.group_ids)

    def rename(self, name: str) -> None:
        self.name = clean_name(name, field="name", missing=_MISSING_NAME)

    def change_groups(self, group_ids: Iterable[GroupId]) -> None:
        # Набор без повторов, порядок не важен
        unique = tuple(sorted(set(group_ids), key=str))
        if not unique:
            raise InvalidValue("Укажите хотя бы одну группу", field="group_ids")
        self.group_ids = unique
