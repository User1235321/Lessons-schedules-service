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


class RoomNameTaken(AlreadyExists):
    """В проекте уже есть аудитория с таким названием."""

    code = "ROOM_NAME_TAKEN"


class StreamNameTaken(AlreadyExists):
    """В проекте уже есть поток с таким названием."""

    code = "STREAM_NAME_TAKEN"


# Удалить то, на что ссылаются другие данные проекта, нельзя: ничего не пропадает молча.
# В details — списки тех, кто ссылается, чтобы пользователь мог их поправить.


class SubjectInUse(Conflict):
    """details: teachers, rooms, workloads."""

    code = "SUBJECT_IN_USE"


class GroupInUse(Conflict):
    """details: streams — потоки с этой группой, workloads — нагрузка группы и её подгрупп."""

    code = "GROUP_IN_USE"


class SubgroupInUse(Conflict):
    """details: workloads."""

    code = "SUBGROUP_IN_USE"


class StreamInUse(Conflict):
    """details: workloads."""

    code = "STREAM_IN_USE"


class SubgroupsExceedGroup(InvalidValue):
    """В подгруппах больше студентов, чем в группе (F_Data_12)."""

    code = "SUBGROUPS_EXCEED_GROUP"
