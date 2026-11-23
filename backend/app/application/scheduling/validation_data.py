from app.application.shared.uow import UnitOfWork
from app.domain.academic.capability import Capability
from app.domain.projects.project import Project
from app.domain.scheduling.job import Job
from app.domain.scheduling.problem import (
    ScheduleProblem,
    WorkloadSnapshot,
    WorkloadTarget,
    WorkloadTargetKind,
)
from app.domain.scheduling.resources import (
    GroupSnapshot,
    RoomSnapshot,
    RoomType,
    StreamSnapshot,
    SubgroupSnapshot,
    SubjectSnapshot,
    TeacherSnapshot,
    TeachingCapability,
    WeeklyWindow,
)
from app.domain.scheduling.schedule import LessonFormat
from app.domain.shared.week import WeeklyInterval


def enqueue_with_snapshot(uow: UnitOfWork, job: Job, project: Project) -> None:
    problem = load_validation_data(uow, project, for_processing=True)
    problem.check_size_limits()
    uow.jobs.add(job)
    uow.jobs.add_problem(job.id, problem)
    uow.job_outbox.add(job.id, job.created_at)


def _windows(intervals: tuple[WeeklyInterval, ...]) -> tuple[WeeklyWindow, ...]:
    return tuple(
        WeeklyWindow(item.week.value, item.day, item.start, item.end) for item in intervals
    )


def _capabilities(capabilities: tuple[Capability, ...]) -> tuple[TeachingCapability, ...]:
    return tuple(
        TeachingCapability(item.subject_id, item.lesson_type.value) for item in capabilities
    )


def load_validation_data(
    uow: UnitOfWork, project: Project, *, for_processing: bool = False
) -> ScheduleProblem:
    project_id = project.id
    groups = uow.groups.list_in_project(project_id)
    return ScheduleProblem(
        settings=project.settings,
        subjects=tuple(
            SubjectSnapshot(subject.id, subject.name)
            for subject in uow.subjects.list_in_project(project_id)
        ),
        optimization_criteria=tuple(uow.criteria.list_in_project(project_id))
        if for_processing
        else (),
        groups=tuple(
            GroupSnapshot(group.id, group.name, group.student_count, _windows(group.availability))
            for group in groups
        ),
        subgroups=tuple(
            SubgroupSnapshot(
                subgroup.id,
                group.id,
                subgroup.name,
                subgroup.student_count,
                _windows(subgroup.availability),
            )
            for group in groups
            for subgroup in group.subgroups
        ),
        streams=tuple(
            StreamSnapshot(stream.id, stream.name, stream.group_ids)
            for stream in uow.streams.list_in_project(project_id)
        ),
        teachers=tuple(
            TeacherSnapshot(
                teacher.id,
                teacher.full_name,
                _capabilities(teacher.capabilities),
                _windows(teacher.availability),
                _windows(teacher.preferences),
            )
            for teacher in uow.teachers.list_in_project(project_id)
        ),
        rooms=tuple(
            RoomSnapshot(
                room.id,
                room.name,
                room.capacity,
                RoomType(room.type),
                _windows(room.availability),
                _capabilities(room.capabilities),
            )
            for room in uow.rooms.list_in_project(project_id)
        ),
        workloads=tuple(
            WorkloadSnapshot(
                workload.id,
                WorkloadTarget(WorkloadTargetKind(workload.target.type), workload.target.id),
                workload.subject_id,
                workload.lesson_type.value,
                LessonFormat(workload.format),
                workload.occurrences_per_cycle,
                workload.required_teacher_count,
                workload.duration_minutes,
            )
            for workload in uow.workloads.list_in_project(project_id)
        ),
        constraints=tuple(uow.constraints.list_in_project(project_id)),
    )
