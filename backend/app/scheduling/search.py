from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from uuid import UUID

from app.domain.projects.settings import ProjectSettings
from app.domain.scheduling.job import JobProgress
from app.domain.scheduling.solver import SolverControl
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
                if subgroup is not None and other_subgroup is not None:
                    if subgroup != other_subgroup:
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
    selected: list[Placement] = []
    iterators: list[Iterator[Placement]] = []
    deepest = 0

    while True:
        check_cancelled(control)
        depth = len(selected)
        if depth == len(tasks):
            yield tuple(selected)
            occupied.remove(selected.pop())
            continue
        if len(iterators) == depth:
            iterators.append(iter_placements(tasks[depth], settings, control))
        try:
            placement = next(iterators[depth])
        except StopIteration:
            iterators.pop()
            if not selected:
                return
            occupied.remove(selected.pop())
            continue
        if (
            depth
            and tasks[depth].workload.id == tasks[depth - 1].workload.id
            and placement.order_key <= selected[-1].order_key
        ):
            continue
        if not occupied.can_place(placement):
            continue
        occupied.add(placement)
        selected.append(placement)
        if len(selected) > deepest:
            deepest = len(selected)
            control.report_progress(JobProgress(min(99, 100 * deepest / len(tasks))))
