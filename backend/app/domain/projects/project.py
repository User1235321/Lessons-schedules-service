from dataclasses import dataclass
from datetime import datetime

from app.domain.projects.settings import ProjectSettings
from app.domain.shared.errors import InvalidValue
from app.domain.shared.ids import ProjectId, UserId

MAX_NAME_LENGTH = 200


@dataclass(kw_only=True)
class Project:
    """Проект расписания. Принадлежит одному пользователю (F_Auth_7, F_Project_3)."""

    id: ProjectId
    owner_id: UserId
    name: str
    settings: ProjectSettings
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.name = _clean_name(self.name)

    @classmethod
    def create(
        cls,
        *,
        project_id: ProjectId,
        owner_id: UserId,
        name: str,
        now: datetime,
        settings: ProjectSettings | None = None,
    ) -> "Project":
        return cls(
            id=project_id,
            owner_id=owner_id,
            name=name,
            settings=settings or ProjectSettings.default(),
            created_at=now,
            updated_at=now,
        )

    def rename(self, name: str, now: datetime) -> None:
        self.name = _clean_name(name)
        self.updated_at = now

    def change_settings(self, settings: ProjectSettings, now: datetime) -> None:
        self.settings = settings
        self.updated_at = now


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:  # F_Project_1
        raise InvalidValue("Укажите название проекта", field="name")
    if len(cleaned) > MAX_NAME_LENGTH:
        raise InvalidValue(f"Название длиннее {MAX_NAME_LENGTH} символов", field="name")
    return cleaned
