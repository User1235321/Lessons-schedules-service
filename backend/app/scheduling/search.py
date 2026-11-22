from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from uuid import UUID

from app.domain.projects.settings import ProjectSettings
from app.domain.scheduling.constraint_validation import constraint_conflicts
from app.domain.scheduling.constraints import (
    ConstraintKind,
    ExtraConstraintSnapshot,
    MinimumGapParameters,
    RelatedWorkloadParameters,
)
from app.domain.scheduling.job import JobProgress
from app.domain.scheduling.schedule import ScheduleEntry
from app.domain.scheduling.solver import SolverControl
from app.domain.shared.ids import ScheduleEntryId
from app.domain.shared.week import Weekday
from app.scheduling.candidates import (
    LessonRequirements,
    Placement,
    check_cancelled,
    iter_placements,
)

ResourceKey = tuple[UUID, str, Weekday]


def _overlaps(first: Placement, second: Placement) -> bool:
    return first.start_time < second.end_time and second.start_time < first.end_time


@dataclass
class ResourceOccupancy:
    groups: dict[ResourceKey, list[Placement]] = field(
        default_factory=lambda: defaultdict(list)
    )
    teachers: dict[ResourceKey, list[Placement]] = field(
        default_factory=lambda: defaultdict(list)
    )
    rooms: dict[ResourceKey, list[Placement]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def _keys(self, placement: Placement) -> Iterator[tuple[dict, ResourceKey]]:
        for group_id in placement.requirements.participants.group_ids:
            yield self.groups, (group_id, placement.week, placement.weekday)
        for teacher in placement.teachers:
            yield self.teachers, (teacher.id, placement.week, placement.weekday)
        if placement.room is not None:
            yield self.rooms, (placement.room.id, placement.week, placement.weekday)

    def can_place(self, placement: Placement) -> bool:
        subgroup = placement.requirements.participants.subgroup_id
        for group_id in placement.requirements.participants.group_ids:
            key = (group_id, placement.week, placement.weekday)
            for existing in self.groups.get(key, ()):
                other_subgroup = existing.requirements.participants.subgroup_id
                if (
                    subgroup is not None
                    and other_subgroup is not None
                    and subgroup != other_subgroup
                ):
                    continue
                if _overlaps(placement, existing):
                    return False
        for teacher in placement.teachers:
            key = (teacher.id, placement.week, placement.weekday)
            if any(_overlaps(placement, other) for other in self.teachers.get(key, ())):
                return False
        if placement.room is not None:
            key = (placement.room.id, placement.week, placement.weekday)
            if any(_overlaps(placement, other) for other in self.rooms.get(key, ())):
                return False
        return True

    def add(self, placement: Placement) -> None:
        for mapping, key in self._keys(placement):
            mapping[key].append(placement)

    def remove(self, placement: Placement) -> None:
        for mapping, key in self._keys(placement):
            mapping[key].pop()


@dataclass
class ConstraintOccupancy:
    constraints: tuple[ExtraConstraintSnapshot, ...]
    occurrences: dict[UUID, int]
    entries: dict[UUID, list[ScheduleEntry]] = field(
        default_factory=lambda: defaultdict(list)
    )
    relevant: dict[UUID, list[ExtraConstraintSnapshot]] = field(init=False)

    def __post_init__(self) -> None:
        self.relevant = defaultdict(list)
        for constraint in self.constraints:
            if constraint.kind is ConstraintKind.EVERY_WEEK:
                self.relevant[constraint.scope.resource_id].append(constraint)
            elif isinstance(
                constraint.parameters, (RelatedWorkloadParameters, MinimumGapParameters)
            ):
                source = constraint.scope.resource_id
                target = constraint.parameters.workload_id
                self.relevant[source].append(constraint)
                if target != source:
                    self.relevant[target].append(constraint)

    def can_place(self, placement: Placement, depth: int) -> bool:
        workload_id = placement.requirements.workload.id
        candidate = placement.to_entry(ScheduleEntryId(UUID(int=depth + 1)))
        for constraint in self.relevant.get(workload_id, ()):
            source = constraint.scope.resource_id
            selected = list(self.entries[source])
            if source == workload_id:
                selected.append(candidate)
            if constraint.kind is ConstraintKind.EVERY_WEEK:
                if len(selected) == self.occurrences[source] and any(
                    constraint_conflicts(constraint, selected, [], True)
                ):
                    return False
                continue
            related_id = constraint.parameters.workload_id
            if related_id == source:
                related = selected
            else:
                related = list(self.entries[related_id])
                if related_id == workload_id:
                    related.append(candidate)
            complete = (
                len(selected) == self.occurrences[source]
                and len(related) == self.occurrences[related_id]
            )
            if constraint.kind in (ConstraintKind.CONSECUTIVE, ConstraintKind.BEFORE):
                if not complete:
                    continue
            if any(constraint_conflicts(constraint, selected, related, complete)):
                return False
        return True

    def add(self, placement: Placement, depth: int) -> None:
        workload_id = placement.requirements.workload.id
        self.entries[workload_id].append(
            placement.to_entry(ScheduleEntryId(UUID(int=depth + 1)))
        )

    def remove(self, placement: Placement) -> None:
        self.entries[placement.requirements.workload.id].pop()


def _difficulty(requirements: LessonRequirements) -> tuple[int, int, int, UUID]:
    teacher_choices = len(requirements.teachers) - requirements.workload.required_teacher_count + 1
    room_choices = max(1, len(requirements.rooms))
    return (
        teacher_choices * room_choices,
        -len(requirements.participants.group_ids),
        -requirements.duration_minutes,
        requirements.workload.id,
    )


def find_placements(
    requirements: tuple[LessonRequirements, ...],
    settings: ProjectSettings,
    control: SolverControl,
    constraints: tuple[ExtraConstraintSnapshot, ...] = (),
) -> Iterator[tuple[Placement, ...]]:
    tasks = tuple(
        requirement
        for requirement in sorted(requirements, key=_difficulty)
        for _ in range(requirement.workload.occurrences_per_cycle)
    )
    if not tasks:
        yield ()
        return

    occupied = ResourceOccupancy()
    constrained = (
        ConstraintOccupancy(
            constraints,
            {item.workload.id: item.workload.occurrences_per_cycle for item in requirements},
        )
        if constraints
        else None
    )
    selected: list[Placement] = []
    iterators: list[Iterator[Placement]] = []
    deepest = 0

    while True:
        check_cancelled(control)
        depth = len(selected)
        if depth == len(tasks):
            yield tuple(selected)
            previous = selected.pop()
            occupied.remove(previous)
            if constrained is not None:
                constrained.remove(previous)
            continue
        if len(iterators) == depth:
            iterators.append(iter_placements(tasks[depth], settings, control))
        try:
            placement = next(iterators[depth])
        except StopIteration:
            iterators.pop()
            if not selected:
                return
            previous = selected.pop()
            occupied.remove(previous)
            if constrained is not None:
                constrained.remove(previous)
            continue
        if (
            depth
            and tasks[depth].workload.id == tasks[depth - 1].workload.id
            and placement.order_key <= selected[-1].order_key
        ):
            continue
        if not occupied.can_place(placement):
            continue
        if constrained is not None and not constrained.can_place(placement, depth):
            continue
        occupied.add(placement)
        if constrained is not None:
            constrained.add(placement, depth)
        selected.append(placement)
        if len(selected) > deepest:
            deepest = len(selected)
            control.report_progress(JobProgress(min(99, 100 * deepest / len(tasks))))
