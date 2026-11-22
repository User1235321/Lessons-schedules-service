from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.scheduling.job import Job
from app.domain.scheduling.problem import ScheduleProblem
from app.domain.shared.errors import NotFound
from app.infrastructure.persistence.mappers.jobs import problem_codec
from app.infrastructure.persistence.models.jobs import JobProblemRow, JobRow


class SqlJobProblemSource:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def load(self, job: Job) -> ScheduleProblem:
        with self._session_factory() as session:
            data = session.scalar(
                select(JobProblemRow.problem)
                .join(JobRow)
                .where(JobProblemRow.job_id == job.id, JobRow.project_id == job.project_id)
            )
            if data is None:
                raise NotFound("Снимок данных задания отсутствует. Запустите расчёт повторно.")
            return problem_codec.validate_python(data)
