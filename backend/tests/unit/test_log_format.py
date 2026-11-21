import json
import logging

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
