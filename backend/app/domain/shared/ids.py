from typing import NewType
from uuid import UUID

# Разные типы для идентификаторов разных сущностей: перепутать их в сигнатуре нельзя.
UserId = NewType("UserId", UUID)
SessionId = NewType("SessionId", UUID)
ProjectId = NewType("ProjectId", UUID)
SubjectId = NewType("SubjectId", UUID)
TeacherId = NewType("TeacherId", UUID)
GroupId = NewType("GroupId", UUID)
SubgroupId = NewType("SubgroupId", UUID)
