from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.domain.projects.settings import ProjectSettings
from app.domain.scheduling.job import JobProgress, ResultMode, ResultOptions
from app.domain.scheduling.problem import (
    ScheduleProblem,
    WorkloadSnapshot,
    WorkloadTarget,
    WorkloadTargetKind,
)
from app.domain.scheduling.schedule import LessonFormat
from app.domain.scheduling.solver import ScheduleVariant, SolverResult, SolverStatus
from app.scheduling.preview import PreviewScheduleSolver


def test_preview_returns_one_empty_variant_for_top_n() -> None:
    control = Mock()
    control.is_cancel_requested.return_value = False
    result = PreviewScheduleSolver().solve(
        ScheduleProblem(ProjectSettings.default()),
        ResultOptions(ResultMode.TOP_N, 3),
        control,
    )
    assert result == SolverResult(SolverStatus.SOLVED, (ScheduleVariant((), ()),))
    control.report_progress.assert_called_once_with(JobProgress(50))


def test_preview_cancels_before_calculation() -> None:
    control = Mock()
    control.is_cancel_requested.return_value = True
    result = PreviewScheduleSolver().solve(
        ScheduleProblem(ProjectSettings.default()), ResultOptions(), control
    )
    assert result == SolverResult(SolverStatus.CANCELLED)
    control.report_progress.assert_not_called()


def test_preview_cancels_after_progress_update() -> None:
    control = Mock()
    control.is_cancel_requested.side_effect = [False, True]
    result = PreviewScheduleSolver().solve(
        ScheduleProblem(ProjectSettings.default()), ResultOptions(), control
    )
    assert result == SolverResult(SolverStatus.CANCELLED)


def test_preview_refuses_to_ignore_real_workload() -> None:
    control = Mock()
    control.is_cancel_requested.return_value = False
    workload = WorkloadSnapshot(
        id=uuid4(),
        target=WorkloadTarget(WorkloadTargetKind.GROUP, uuid4()),
        subject_id=uuid4(),
        lesson_type="LECTURE",
        lesson_format=LessonFormat.ONSITE,
        occurrences_per_cycle=1,
        required_teacher_count=1,
    )
    problem = ScheduleProblem(ProjectSettings.default(), workloads=(workload,))
    with pytest.raises(NotImplementedError, match="учебной нагрузке"):
        PreviewScheduleSolver().solve(problem, ResultOptions(), control)
