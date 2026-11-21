import logging
from contextvars import ContextVar
from time import monotonic
from uuid import uuid4

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
logger = logging.getLogger(__name__)


def get_request_id() -> str | None:
    return _request_id.get()


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        token = _request_id.set(request_id)
        started_at = monotonic()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            route = scope.get("route")
            extra: dict[str, object] = {
                "event": "http.request.completed",
                "method": scope["method"],
                "route": route.path if route is not None else "<unmatched>",
                "status_code": status_code,
                "duration_ms": round((monotonic() - started_at) * 1000, 2),
            }
            job_id = scope.get("path_params", {}).get("job_id")
            if job_id is not None:
                extra["job_id"] = str(job_id)
            try:
                logger.info("HTTP request completed", extra=extra)
            finally:
                _request_id.reset(token)
