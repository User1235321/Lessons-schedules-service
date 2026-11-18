from datetime import UTC, datetime, time
from uuid import uuid4

from app.api.schemas.jobs import ScheduleResponse
from app.domain.scheduling.schedule import (
    CriterionScore,
    Schedule,
    ScheduleEntry,
    ScheduleSource,
    TeacherAssignment,
)
from app.domain.shared.ids import JobId, ProjectId, ScheduleEntryId, ScheduleId
from app.domain.shared.week import Weekday


def test_schedule_response_matches_api_contract() -> None:
    job_id = JobId(uuid4())
    schedule = Schedule(
        id=ScheduleId(uuid4()),
        project_id=ProjectId(uuid4()),
        job_id=job_id,
        source=ScheduleSource.GENERATED,
        result_index=1,
        created_at=datetime.now(UTC),
        criterion_scores=(CriterionScore("gaps", 2.5),),
        entries=(
            ScheduleEntry(
                id=ScheduleEntryId(uuid4()),
                workload_id=uuid4(),
                week="ODD",
                weekday=Weekday.MONDAY,
                start_time=time(9),
                end_time=time(10, 40),
                teachers=(TeacherAssignment("Иванов"),),
            ),
        ),
    )
    response = ScheduleResponse.of(schedule).model_dump(mode="json")
    assert response["job_id"] == str(job_id)
    assert response["source"] == "GENERATED"
    assert response["criterion_scores"] == {"gaps": 2.5}
    assert response["entries"][0]["start_time"] == "09:00"
    assert response["entries"][0]["end_time"] == "10:40"
    assert response["entries"][0]["teachers"] == [
        {"teacher_id": None, "display_name": "Иванов"}
    ]
