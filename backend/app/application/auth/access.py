from app.application.shared.uow import UnitOfWork
from app.domain.projects.project import Project
from app.domain.shared.errors import NotFound
from app.domain.shared.ids import ProjectId, UserId


def owned_project(uow: UnitOfWork, project_id: ProjectId, user_id: UserId) -> Project:
    """Проект пользователя (F_Auth_7, HLD 8).

    Вызывается внутри транзакции сценария до любой операции с проектом и его данными.
    Чужой проект неотличим от несуществующего: оба дают NotFound (NF_Security_2).
    """
    project = uow.projects.get_owned(project_id, user_id)
    if project is None:
        raise NotFound("Проект не найден", project_id=str(project_id))
    return project
