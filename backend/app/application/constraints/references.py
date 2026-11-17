from uuid import UUID

from app.application.shared.uow import UnitOfWork
from app.domain.shared.errors import Conflict
from app.domain.shared.ids import ProjectId


def ensure_not_referenced(
    uow: UnitOfWork, project_id: ProjectId, resource_type: str, resource_ids: set[UUID]
) -> None:
    uow.constraints.lock_project(project_id)
    references = uow.constraints.referencing(project_id, resource_type, resource_ids)
    if references:
        raise Conflict(
            "Ресурс используется в дополнительных ограничениях",
            constraints=[str(constraint_id) for constraint_id in references],
        )
