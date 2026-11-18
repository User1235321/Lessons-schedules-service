from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.scheduling.job import Job
from app.domain.scheduling.problem import ScheduleProblem
from app.domain.shared.errors import NotFound
from app.infrastructure.persistence.mappers.projects import project_to_domain
from app.infrastructure.persistence.models.projects import ProjectRow


class SqlJobProblemSource:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def load(self, job: Job) -> ScheduleProblem:
        with self._session_factory() as session:
            row = session.scalar(select(ProjectRow).where(ProjectRow.id == job.project_id))
            if row is None:
                raise NotFound("Проект задания не найден", project_id=str(job.project_id))
            return ScheduleProblem(settings=project_to_domain(row).settings)
