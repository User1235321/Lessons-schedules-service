from typing import Protocol

from app.domain.projects.project import Project
from app.domain.shared.ids import ProjectId, UserId


class ProjectRepository(Protocol):
    def add(self, project: Project) -> None: ...

    def get_owned(self, project_id: ProjectId, owner_id: UserId) -> Project | None:
        """Проект, если он принадлежит owner_id.

        Чужой проект неотличим от несуществующего (NF_Security_2).
        """
        ...

    def list_owned(self, owner_id: UserId) -> list[Project]:
        """Проекты пользователя, сначала недавно изменённые."""
        ...

    def save(self, project: Project) -> None:
        """Записывает изменения. Владелец и время создания не меняются.

        Если у project.owner_id нет такого проекта — NotFound.
        """
        ...

    def delete(self, project_id: ProjectId, owner_id: UserId) -> None:
        """Удаляет проект вместе с его данными. Чужой или несуществующий — NotFound."""
        ...
