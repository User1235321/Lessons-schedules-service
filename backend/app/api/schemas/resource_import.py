import json
from uuid import UUID

from pydantic import ValidationError

from app.api.schemas import academic, academic_resources
from app.api.schemas.constraints import CreateConstraintRequest, UpdateConstraintRequest
from app.api.schemas.table_rows import import_rows
from app.api.schemas.transfer_values import check_storage_values
from app.application.import_export.resources import ResourceChange
from app.application.import_export.schedules import ImportIssue
from app.domain.shared.errors import InvalidValue

SCHEMAS = {
    "subjects": (academic.SubjectRequest, academic.SubjectUpdateRequest),
    "groups": (academic.GroupRequest, academic.GroupUpdateRequest),
    "subgroups": (academic.SubgroupRequest, academic.SubgroupUpdateRequest),
    "teachers": (academic.TeacherRequest, academic.TeacherUpdateRequest),
    "rooms": (academic_resources.RoomRequest, academic_resources.RoomUpdateRequest),
    "streams": (academic_resources.StreamRequest, academic_resources.StreamUpdateRequest),
    "workloads": (academic_resources.WorkloadRequest, academic_resources.WorkloadUpdateRequest),
    "constraints": (CreateConstraintRequest, UpdateConstraintRequest),
}

_NESTED = {"capabilities", "availability", "preferences", "group_ids", "scope", "parameters"}


def resource_change(resource: str, data: dict, existing_id: UUID | None) -> ResourceChange:
    create, update = SCHEMAS[resource]
    schema = update if existing_id is not None else create
    unknown = data.keys() - schema.model_fields.keys()
    if unknown:
        raise InvalidValue("Неизвестное поле ресурса", field=str(next(iter(unknown))))
    if not data:
        raise InvalidValue("Нет выбранных полей", field="mapping")
    body = schema.model_validate(data)
    check_storage_values(body.model_dump(exclude_unset=True))
    if resource == "subjects":
        args = (body.name,)
    elif resource in ("groups", "subgroups"):
        args = (body.name, body.student_count, body.to_availability())
        if resource == "subgroups" and existing_id is None:
            args = (body.group_id, *args)
    else:
        args = (body.to_changes() if existing_id is not None else body.to_draft(),)
    return ResourceChange(resource, existing_id, args)


def resource_rows(content, extension, resource, mapping):
    for number, raw in import_rows(content, extension, "rows"):
        if isinstance(raw, ImportIssue):
            yield number, raw
            continue
        try:
            if not isinstance(raw, dict):
                raise InvalidValue("Ожидается объект с полями ресурса", field="row")
            values = {
                mapping.get(key, key): value
                for key, value in raw.items()
                if not mapping or key in mapping
            }
            identifier = values.pop("id", raw.get("id"))
            try:
                existing = UUID(str(identifier)) if identifier not in (None, "") else None
            except ValueError:
                raise InvalidValue("Некорректный UUID", field="id") from None
            if extension != "json":
                values = {k: v for k, v in values.items() if v not in ("", None)}
                for key in values.keys() & _NESTED:
                    if isinstance(values[key], str):
                        try:
                            values[key] = json.loads(values[key])
                        except ValueError:
                            raise InvalidValue("Ожидается JSON в ячейке", field=key) from None
            yield number, resource_change(resource, values, existing)
        except ValidationError as error:
            for item in error.errors():
                yield number, ImportIssue(number, ".".join(map(str, item["loc"])), item["msg"])
        except InvalidValue as error:
            yield number, ImportIssue(number, error.field, error.message)
