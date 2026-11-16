import json
from uuid import UUID

from app.domain.scheduling.job import JobMessage, JobType
from app.domain.shared.ids import JobId, ProjectId

JOBS_TOPIC = "schedule.jobs"


def encode_job_message(message: JobMessage) -> bytes:
    return json.dumps(
        {
            "job_id": str(message.job_id),
            "project_id": str(message.project_id),
            "job_type": message.job_type.value,
        }
    ).encode("utf-8")


def decode_job_message(payload: bytes) -> JobMessage:
    try:
        data = json.loads(payload)
        return JobMessage(
            JobId(UUID(data["job_id"])),
            ProjectId(UUID(data["project_id"])),
            JobType(data["job_type"]),
        )
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        raise ValueError("Некорректное сообщение задания") from error
