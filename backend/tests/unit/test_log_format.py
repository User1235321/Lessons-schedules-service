import json
import logging
import sys

from app.infrastructure.logging import JsonFormatter


def test_json_formatter_includes_request_context_and_event() -> None:
    formatter = JsonFormatter(lambda: "request-123")
    record = logging.makeLogRecord(
        {
            "name": "app.api",
            "levelno": logging.INFO,
            "levelname": "INFO",
            "msg": "HTTP request completed",
            "args": (),
            "event": "http.request.completed",
            "status_code": 200,
            "job_id": "job-123",
        }
    )

    payload = json.loads(formatter.format(record))

    assert payload["service"] == "backend"
    assert payload["level"] == "INFO"
    assert payload["event"] == "http.request.completed"
    assert payload["request_id"] == "request-123"
    assert payload["status_code"] == 200
    assert payload["job_id"] == "job-123"
    assert payload["timestamp"].endswith("Z")


def test_json_formatter_omits_request_id_outside_http_context() -> None:
    formatter = JsonFormatter()
    record = logging.makeLogRecord(
        {"name": "app.bootstrap.delivery", "levelno": logging.WARNING, "msg": "Failed"}
    )

    payload = json.loads(formatter.format(record))

    assert "request_id" not in payload
    assert payload["event"] == "log.message"

def test_json_formatter_prefers_explicit_request_id() -> None:
    formatter = JsonFormatter(lambda: "context-id")
    record = logging.makeLogRecord(
        {
            "name": "app.api.errors",
            "levelno": logging.ERROR,
            "msg": "Unhandled HTTP exception",
            "request_id": "response-id",
        }
    )

    payload = json.loads(formatter.format(record))

    assert payload["request_id"] == "response-id"


def test_json_formatter_includes_exception_message_and_traceback_without_secrets() -> None:
    formatter = JsonFormatter()
    try:
        raise RuntimeError(
            "Authorization: Bearer exposed-token for student@example.org"
        )
    except RuntimeError:
        exception_info = sys.exc_info()

    record = logging.makeLogRecord(
        {
            "name": "app.api.errors",
            "levelno": logging.ERROR,
            "msg": "Unhandled HTTP exception",
            "exc_info": exception_info,
        }
    )
    payload = json.loads(formatter.format(record))

    assert "RuntimeError:" in payload["traceback"]
    assert "test_log_format.py" in payload["traceback"]
    assert "exposed-token" not in payload["traceback"]
    assert "student@example.org" not in payload["traceback"]
    assert "[REDACTED]" in payload["traceback"]


def test_json_formatter_redacts_database_exception_details() -> None:
    from sqlalchemy.exc import IntegrityError

    formatter = JsonFormatter()
    try:
        raise IntegrityError("INSERT INTO users", {"password": "plaintext"}, Exception("db"))
    except IntegrityError:
        exception_info = sys.exc_info()

    record = logging.makeLogRecord(
        {
            "name": "app.infrastructure.persistence",
            "levelno": logging.ERROR,
            "msg": "Database operation failed",
            "exc_info": exception_info,
        }
    )
    payload = json.loads(formatter.format(record))

    assert "IntegrityError: [details redacted]" in payload["traceback"]
    assert "plaintext" not in payload["traceback"]
    assert "INSERT INTO users" not in payload["traceback"]
