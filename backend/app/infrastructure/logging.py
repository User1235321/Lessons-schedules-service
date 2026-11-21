import json
import logging
import sys
import traceback
from collections.abc import Callable
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def __init__(self, request_id_provider: Callable[[], str | None] | None = None) -> None:
        super().__init__()
        self.request_id_provider = request_id_provider

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "service": "backend",
            "logger": record.name,
            "event": getattr(record, "event", "log.message"),
            "message": record.getMessage(),
        }
        request_id = self.request_id_provider() if self.request_id_provider else None
        if request_id:
            payload["request_id"] = request_id
        for field in (
            "method",
            "route",
            "status_code",
            "duration_ms",
            "job_id",
            "job_status",
            "error_code",
            "exception_type",
        ):
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__
            payload["traceback"] = "".join(traceback.format_tb(record.exc_info[2]))
        return json.dumps(payload, ensure_ascii=False)


class StdoutHandler(logging.StreamHandler):
    def emit(self, record: logging.LogRecord) -> None:
        self.stream = sys.stdout
        super().emit(record)


def configure_logging(
    level: str, request_id_provider: Callable[[], str | None] | None = None
) -> None:
    root = logging.getLogger()
    handler = next((item for item in root.handlers if item.name == "backend-json"), None)
    if handler is None:
        handler = StdoutHandler()
        handler.set_name("backend-json")
        root.addHandler(handler)
    handler.setFormatter(JsonFormatter(request_id_provider))
    root.setLevel(level)

    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.handlers.clear()
    uvicorn_logger.propagate = True
    error_logger = logging.getLogger("uvicorn.error")
    error_logger.handlers.clear()
    error_logger.propagate = True
    logging.getLogger("uvicorn.access").disabled = True
