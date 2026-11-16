from app.domain.shared.errors import AlreadyExists, Conflict, InvalidValue


class SubjectNameTaken(AlreadyExists):
    """В проекте уже есть дисциплина с таким названием."""

    code = "SUBJECT_NAME_TAKEN"


class GroupNameTaken(AlreadyExists):
    """В проекте уже есть группа с таким названием."""

    code = "GROUP_NAME_TAKEN"


class SubgroupNameTaken(AlreadyExists):
    """В группе уже есть подгруппа с таким названием."""

    code = "SUBGROUP_NAME_TAKEN"


class SubjectInUse(Conflict):
    """Дисциплину нельзя удалить, пока на неё ссылаются. В details — кто ссылается."""

    code = "SUBJECT_IN_USE"


class SubgroupsExceedGroup(InvalidValue):
    """В подгруппах больше студентов, чем в группе (F_Data_12)."""

    code = "SUBGROUPS_EXCEED_GROUP"
