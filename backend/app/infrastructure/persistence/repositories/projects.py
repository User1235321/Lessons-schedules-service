from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.domain.projects.project import Project
from app.domain.shared.errors import NotFound
from app.domain.shared.ids import ProjectId, UserId
from app.infrastructure.persistence.mappers.projects import (
    fill_project_row,
    project_to_domain,
    project_to_row,
)
from app.infrastructure.persistence.models import ProjectRow


class SqlProjectRepository:
    """Реализует ProjectRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, project: Project) -> None:
        self._session.add(project_to_row(project))

    def get_owned(self, project_id: ProjectId, owner_id: UserId) -> Project | None:
        row = self._session.scalar(
            select(ProjectRow).where(ProjectRow.id == project_id, ProjectRow.owner_id == owner_id)
        )
        return project_to_domain(row) if row else None

    def list_owned(self, owner_id: UserId) -> list[Project]:
        rows = self._session.scalars(
            select(ProjectRow)
            .where(ProjectRow.owner_id == owner_id)
            .order_by(ProjectRow.updated_at.desc(), ProjectRow.id)
        )
        return [project_to_domain(row) for row in rows]

    def save(self, project: Project) -> None:
        # Строка, прочитанная в этой же транзакции, берётся из сессии без нового запроса
        row = self._session.get(ProjectRow, project.id)
        if row is None:
            raise NotFound("Проект не найден", project_id=str(project.id))
        fill_project_row(row, project)

    def delete(self, project_id: ProjectId) -> None:
        # Данные проекта удалит база: внешние ключи на projects объявлены с ON DELETE CASCADE
        self._session.execute(delete(ProjectRow).where(ProjectRow.id == project_id))
