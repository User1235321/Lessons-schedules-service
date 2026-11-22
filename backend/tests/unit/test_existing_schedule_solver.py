from dataclasses import replace
from datetime import UTC, datetime, time
from unittest.mock import Mock
from uuid import uuid4

from app.domain.projects.settings import ProjectSettings
from app.domain.scheduling.job import ExistingScheduleInput, JobType
from app.domain.scheduling.problem import OptimizationCriterionSnapshot, ScheduleProblem
from app.domain.scheduling.schedule import Schedule, ScheduleEntry, ScheduleSource
from app.domain.scheduling.solver import SolverStatus
from app.domain.shared.week import Weekday
from app.scheduling.reprocessing import ExistingScheduleSolver


def test_modes_rank_changes_before_quality_only_for_min_changes():
    entry = ScheduleEntry(
        id=uuid4(), week="ODD", weekday=Weekday.MONDAY, start_time=time(5), end_time=time(6, 40)
    )
    schedule = Schedule(
        id=uuid4(),
        project_id=uuid4(),
        source=ScheduleSource.IMPORTED,
        entries=(entry,),
        created_at=datetime.now(UTC),
    )
    source = ExistingScheduleInput(schedule=schedule)
    problem = ScheduleProblem(
        ProjectSettings.default(),
        optimization_criteria=(OptimizationCriterionSnapshot("EARLY_LATE_CLASSES", 1),),
    )
    solver = ExistingScheduleSolver()
    control = Mock()
    control.is_cancel_requested.return_value = False
    minimal = solver.solve(source, JobType.REOPTIMIZE_MIN_CHANGES, problem, control)
    full = solver.solve(source, JobType.REOPTIMIZE_FULL, problem, control)
    assert minimal.variants[0].entries == (entry,)
    assert minimal.variants[0].criterion_scores[0].value == 1
    assert full.variants[0].entries[0].start_time >= time(8)
    assert full.variants[0].criterion_scores[0].value == 0
    invalid = replace(schedule, entries=(replace(entry, weekday=Weekday.SUNDAY),))
    locked = ExistingScheduleInput(schedule=invalid, fixed_entry_ids=(entry.id,))
    assert (
        solver.solve(locked, JobType.AUTO_REPAIR, problem, control).status
        is SolverStatus.INFEASIBLE
    )
    control.is_cancel_requested.return_value = True
    assert (
        solver.solve(source, JobType.AUTO_REPAIR, problem, control).status is SolverStatus.CANCELLED
    )
