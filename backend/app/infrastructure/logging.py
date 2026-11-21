import json
import logging
import re
import sys
import traceback
from collections.abc import Callable
from datetime import UTC, datetime

_SENSITIVE_VALUES = re.compile(
    r"""\b(authorization|password|passwd|secret|access_token|refresh_token|token|api_key)"""
    r"""\b["']?\s*(?::|=|\bis\b)\s*(?:bearer\s+)?(?:"[^"]*"|'[^']*'|[^\s,;]+)""",
    re.IGNORECASE,
)
_EMAIL_ADDRESSES = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_SENSITIVE_EXCEPTION_MODULES = {"sqlalchemy", "psycopg", "smtplib"}


def redact_sensitive_details(value: str) -> str:
    value = _SENSITIVE_VALUES.sub(lambda m: f"{m.group(1)}=[REDACTED]", value)
    return _EMAIL_ADDRESSES.sub("[REDACTED_EMAIL]", value)


def format_diagnostic_exception(record: logging.LogRecord) -> str:
    exception_type, exception, tb = record.exc_info
    if any(
        cls.__module__.split(".", 1)[0] in _SENSITIVE_EXCEPTION_MODULES
        for cls in exception_type.__mro__
    ):
        frames = "".join(
            f'  File "{frame.filename}", line {frame.lineno}, in {frame.name}\n'
            for frame in traceback.extract_tb(tb)
        )
        return (
            f"Traceback (most recent call last):\n{frames}"
            f"{exception_type.__name__}: [details redacted]"
        )
    return redact_sensitive_details(
        "".join(traceback.format_exception(exception_type, exception, tb, chain=False))
    )


class JsonFormatter(logging.Formatter):
    def __init__(self, request_id_provider: Callable[[], str | None] | None = None) -> None:
        super().__init__()
        self.request_id_provider = request_id_provider

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat().replace(
                "+00:00", "Z"
            ),
            "level": record.levelname,
            "service": "backend",
            "logger": record.name,
            "event": getattr(record, "event", "log.message"),
            "message": redact_sensitive_details(record.getMessage()),
        }
        request_id = getattr(record, "request_id", None)
        if request_id is None and self.request_id_provider:
            request_id = self.request_id_provider()
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
            payload["traceback"] = format_diagnostic_exception(record)
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
