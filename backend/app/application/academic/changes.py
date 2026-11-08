from datetime import datetime

from app.application.shared.uow import UnitOfWork
from app.domain.projects.project import Project


def project_data_changed(uow: UnitOfWork, project: Project, now: datetime) -> None:
    """Правка исходных данных — тоже изменение проекта: он поднимается в списке.

    Вызывается последней в транзакции, после записи самих данных, чтобы строки
    блокировались всегда в одном порядке.
    """
    project.touch(now)
    uow.projects.save(project)
