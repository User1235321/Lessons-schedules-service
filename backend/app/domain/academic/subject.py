from dataclasses import dataclass

from app.domain.academic.names import clean_name
from app.domain.shared.ids import ProjectId, SubjectId

_MISSING_NAME = "Укажите название дисциплины"


@dataclass(kw_only=True)
class Subject:
    """Дисциплина проекта (HLD 9.1.1). Название уникально в проекте без учёта регистра."""

    id: SubjectId
    project_id: ProjectId
    name: str

    def __post_init__(self) -> None:
        self.name = clean_name(self.name, field="name", missing=_MISSING_NAME)

    def rename(self, name: str) -> None:
        self.name = clean_name(name, field="name", missing=_MISSING_NAME)
