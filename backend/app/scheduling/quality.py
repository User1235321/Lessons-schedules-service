from collections import defaultdict
from datetime import time
from itertools import pairwise

from app.domain.scheduling.constraint_validation import covered_by
from app.domain.scheduling.problem import CriterionType, ScheduleProblem, WorkloadTargetKind
from app.domain.scheduling.schedule import CriterionScore, ScheduleEntry


def criterion_scores(
    entries: tuple[ScheduleEntry, ...], problem: ScheduleProblem
) -> tuple[CriterionScore, ...]:
    criteria = sorted(
        (c for c in problem.optimization_criteria if c.is_active), key=lambda c: c.priority
    )
    if not criteria:
        return ()
    students = defaultdict(list)
    teachers = defaultdict(list)
    workloads = {w.id: w for w in problem.workloads}
    streams = {s.id: s.group_ids for s in problem.streams}
    subgroups = defaultdict(list)
    for subgroup in problem.subgroups:
        subgroups[subgroup.group_id].append(subgroup.id)
    preferences = {t.id: t.preferences for t in problem.teachers if t.preferences}
    missed_preferences = 0
    early_late = 0
    for entry in entries:
        day = (entry.week, entry.weekday)
        for teacher in entry.teachers:
            teachers[(teacher.teacher_id or teacher.display_name, day)].append(entry)
            windows = preferences.get(teacher.teacher_id)
            if windows and not covered_by(windows, entry):
                missed_preferences += 1
        workload = workloads.get(entry.workload_id)
        if workload:
            target = workload.target
            if target.kind is WorkloadTargetKind.SUBGROUP:
                participants = (target.resource_id,)
            else:
                groups = (
                    streams.get(target.resource_id, ())
                    if target.kind is WorkloadTargetKind.STREAM
                    else (target.resource_id,)
                )
                participants = [p for group in groups for p in (subgroups[group] or [group])]
        else:
            participants = (entry.participant_label,) if entry.participant_label else ()
        for participant in participants:
            students[participant, day].append(entry)
        early_late += int(entry.start_time < time(8) or entry.end_time > time(18))

    def gaps(days):
        total = 0
        for lessons in days.values():
            ordered = sorted(lessons, key=lambda entry: entry.start_time)
            total += sum(left.end_time < right.start_time for left, right in pairwise(ordered))
        return total

    values = {
        CriterionType.STUDENT_GAPS: gaps(students),
        CriterionType.TEACHER_GAPS: gaps(teachers),
        CriterionType.TEACHER_PREFERENCES: missed_preferences,
        # При фиксированном числе занятий сумма квадратов минимальна при равномерной нагрузке.
        CriterionType.BALANCED_STUDENT_LOAD: sum(
            len(day) * (len(day) - 1) for day in students.values()
        ),
        CriterionType.EARLY_LATE_CLASSES: early_late,
    }
    return tuple(CriterionScore(c.criterion_type, values[c.criterion_type]) for c in criteria)
