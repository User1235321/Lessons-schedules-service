import json
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, FiniteFloat, ValidationError

from app.api.schemas import academic, academic_resources
from app.api.schemas.constraints import ConstraintResponse, CriterionSchema
from app.api.schemas.jobs import ScheduleResponse
from app.api.schemas.projects import CreateProjectRequest, ProjectResponse
from app.api.schemas.resource_import import resource_change
from app.api.schemas.schedule_import import ImportedEntry
from app.api.schemas.transfer_values import check_storage_values
from app.application.import_export.projects import ArchivedResource, ProjectContents, ProjectRestore
from app.application.import_export.resources import OPERATIONS
from app.application.shared.ports import IdGenerator
from app.domain.files import MAX_UPLOAD_BYTES
from app.domain.scheduling.schedule import CriterionScore, Schedule, ScheduleSource
from app.domain.shared.errors import InvalidValue
from app.domain.shared.ids import ProjectId, ScheduleEntryId, ScheduleId


class PortableSchedule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    created_at: AwareDatetime
    result_index: int | None = Field(gt=0, le=2**31 - 1)
    criterion_scores: dict[str, FiniteFloat] | None
    entries: list[dict]


class Archive(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1]
    project: CreateProjectRequest
    subjects: list[dict]
    groups: list[dict]
    subgroups: list[dict]
    teachers: list[dict]
    rooms: list[dict]
    streams: list[dict]
    workloads: list[dict]
    constraints: list[dict]
    criteria: list[CriterionSchema]
    schedules: list[PortableSchedule]


def encode_project(contents: ProjectContents) -> bytes:
    project = ProjectResponse.of(contents.project).model_dump(
        mode="json", exclude={"id", "created_at", "updated_at"}
    )
    groups, subgroups = [], []
    for group in contents.groups:
        row = academic.GroupResponse.of(group).model_dump(mode="json")
        subgroups.extend(dict(s, group_id=row["id"]) for s in row.pop("subgroups"))
        groups.append(row)
    schedules = []
    for schedule in contents.schedules:
        data = ScheduleResponse.of(schedule).model_dump(
            mode="json", include={"entries", "result_index", "criterion_scores"}
        )
        for entry in data["entries"]:
            del entry["id"]
        schedules.append(dict(data, created_at=schedule.created_at.isoformat()))
    document = {
        "version": 1,
        "project": project,
        "groups": groups,
        "subgroups": subgroups,
        "subjects": [
            academic.SubjectResponse.of(x).model_dump(mode="json") for x in contents.subjects
        ],
        "teachers": [
            academic.TeacherResponse.of(x).model_dump(mode="json") for x in contents.teachers
        ],
        "rooms": [
            academic_resources.RoomResponse.of(x).model_dump(mode="json") for x in contents.rooms
        ],
        "streams": [
            academic_resources.StreamResponse.of(x).model_dump(mode="json")
            for x in contents.streams
        ],
        "workloads": [
            academic_resources.WorkloadResponse.of(x).model_dump(mode="json")
            for x in contents.workloads
        ],
        "constraints": [
            ConstraintResponse.of(contents.project.id, x).model_dump(
                mode="json", exclude={"project_id"}
            )
            for x in contents.constraints
        ],
        "criteria": [CriterionSchema.of(x).model_dump(mode="json") for x in contents.criteria],
        "schedules": schedules,
    }
    content = json.dumps(
        document, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")

    if len(content) > MAX_UPLOAD_BYTES:
        raise InvalidValue("Архив превышает лимит обратной загрузки 16 МиБ", field="file_format")
    return content


_REFERENCES = {
    "subject_id": "subjects",
    "group_id": "groups",
    "subgroup_id": "subgroups",
    "stream_id": "streams",
    "teacher_id": "teachers",
    "room_id": "rooms",
    "workload_id": "workloads",
}
_SCOPES = {"GROUP": "groups", "SUBGROUP": "subgroups", "STREAM": "streams", "WORKLOAD": "workloads"}


class ArchiveIds:
    def __init__(self, archive: Archive, ids: IdGenerator):
        self.ids = ids
        self.by_kind = {kind: {} for kind in OPERATIONS}
        for kind, mapping in self.by_kind.items():
            for index, row in enumerate(getattr(archive, kind), 1):
                try:
                    original = UUID(str(row.get("id")))
                except ValueError:
                    raise InvalidValue("Нужен UUID записи", field=f"{kind}.{index}.id") from None
                if original in mapping:
                    raise InvalidValue("Повторяющийся идентификатор", field=f"{kind}.{index}.id")
                mapping[original] = ids.new_id()

    def lookup(self, kind, value, field, *, historical=False):
        if value is None:
            return None
        try:
            original = UUID(str(value))
        except ValueError:
            raise InvalidValue("Некорректная ссылка", field=field) from None
        mapping = self.by_kind[kind]
        if original not in mapping:
            if not historical:
                raise InvalidValue("В архиве отсутствует связанный ресурс", field=field)
            # В старом расписании может остаться идентификатор уже удалённого ресурса.
            mapping[original] = self.ids.new_id()
        return str(mapping[original])

    def remap(self, row, *, historical=False):
        if isinstance(row, list):
            return [self.remap(item, historical=historical) for item in row]
        if not isinstance(row, dict):
            return row
        result = {}
        for key, value in row.items():
            if key in _REFERENCES:
                result[key] = self.lookup(_REFERENCES[key], value, key, historical=historical)
            elif key == "group_ids" and isinstance(value, list):
                result[key] = [self.lookup("groups", item, key) for item in value]
            elif key == "scope" and isinstance(value, dict) and value.get("id") is not None:
                kind = (
                    _SCOPES.get(value.get("type")) if isinstance(value.get("type"), str) else None
                )
                if kind is None:
                    raise InvalidValue("Неизвестная область ограничения", field="scope")
                result[key] = dict(value, id=self.lookup(kind, value["id"], "scope.id"))
            else:
                result[key] = self.remap(value, historical=historical)
        return result


def prepare_project(content: bytes, ids: IdGenerator, destination: ProjectId) -> ProjectRestore:
    try:
        archive = Archive.model_validate_json(content)
        if archive.project.model_fields_set != set(CreateProjectRequest.model_fields):
            raise InvalidValue("В архиве нужны все настройки проекта", field="project")
        check_storage_values(archive.project.model_dump())
        mapping = ArchiveIds(archive, ids)
        resources = []
        for kind in OPERATIONS:
            for number, row in enumerate(getattr(archive, kind), 1):
                old = UUID(str(row["id"]))
                values = mapping.remap({k: v for k, v in row.items() if k != "id"})
                resources.append(
                    ArchivedResource(
                        mapping.by_kind[kind][old], number, resource_change(kind, values, None)
                    )
                )
        schedules = []
        for source in archive.schedules:
            entries = []
            for row in source.entries:
                check_storage_values(row)
                entry = ImportedEntry.model_validate(mapping.remap(row, historical=True)).to_entry(
                    ScheduleEntryId(ids.new_id())
                )
                entries.append(entry)
            scores = source.criterion_scores
            schedules.append(
                Schedule(
                    id=ScheduleId(ids.new_id()),
                    project_id=destination,
                    source=ScheduleSource.IMPORTED,
                    created_at=source.created_at,
                    result_index=source.result_index,
                    entries=tuple(entries),
                    criterion_scores=None
                    if scores is None
                    else tuple(CriterionScore(k, v) for k, v in scores.items()),
                )
            )
        return ProjectRestore(
            archive.project.name,
            archive.project.settings_changes(),
            resources,
            tuple(c.to_domain() for c in archive.criteria),
            schedules,
        )
    except ValidationError as error:
        first = error.errors()[0]
        raise InvalidValue(first["msg"], field=".".join(map(str, first["loc"])) or "file") from None
    except RecursionError:
        raise InvalidValue("Слишком глубокая структура JSON", field="file") from None
