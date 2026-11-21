import json
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.bootstrap.api import create_app


def test_http_response_has_unique_request_id() -> None:
    client = TestClient(create_app())

    first = client.get("/health")
    second = client.get("/health")

    assert first.status_code == second.status_code == 200
    assert UUID(first.headers["X-Request-ID"])
    assert UUID(second.headers["X-Request-ID"])
    assert first.headers["X-Request-ID"] != second.headers["X-Request-ID"]


def test_http_access_log_contains_request_id_and_route(capsys) -> None:
    client = TestClient(create_app())
    capsys.readouterr()

    response = client.get("/health")
    lines = capsys.readouterr().out.splitlines()
    events = [json.loads(line) for line in lines if line.startswith("{")]
    completed = [event for event in events if event.get("event") == "http.request.completed"]

    assert len(completed) == 1
    assert completed[0]["request_id"] == response.headers["X-Request-ID"]
    assert completed[0]["method"] == "GET"
    assert completed[0]["route"] == "/health"
    assert completed[0]["status_code"] == 200


def test_error_responses_always_have_request_id() -> None:
    app = create_app()
    router = APIRouter()

    @router.get("/_test/crash")
    def crash() -> None:
        raise RuntimeError("boom")

    @router.get("/_test/query")
    def query(required: int) -> dict[str, int]:
        return {"required": required}

    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=False)

    for path, status_code in (
        ("/missing-route", 404),
        ("/_test/query", 422),
        ("/_test/crash", 500),
    ):
        response = client.get(path)
        assert response.status_code == status_code
        assert UUID(response.headers["X-Request-ID"])


def test_request_id_is_not_reused_between_parallel_requests() -> None:
    client = TestClient(create_app())

    with ThreadPoolExecutor(max_workers=4) as executor:
        responses = list(executor.map(lambda _: client.get("/health"), range(8)))

    request_ids = [response.headers["X-Request-ID"] for response in responses]
    assert len(set(request_ids)) == len(request_ids)

def test_unhandled_exception_log_correlates_with_error_response(capsys) -> None:
    app = create_app()
    router = APIRouter()

    @router.get("/_test/correlation")
    def crash() -> None:
        raise RuntimeError("diagnostic failure")

    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=False)
    capsys.readouterr()

    response = client.get("/_test/correlation")
    events = [
        json.loads(line)
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("{")
    ]
    errors = [event for event in events if event.get("event") == "http.request.unhandled_error"]

    assert response.status_code == 500
    assert len(errors) == 1
    assert errors[0]["request_id"] == response.headers["X-Request-ID"]
    assert errors[0]["exception_type"] == "RuntimeError"
    assert "RuntimeError: diagnostic failure" in errors[0]["traceback"]
    assert "test_request_logging.py" in errors[0]["traceback"]
