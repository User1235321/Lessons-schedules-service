import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain.files import FileTooLarge, UnsupportedFileFormat
from app.domain.scheduling.errors import JobNotCancellable, JobResultsUnavailable
from app.domain.shared.errors import (
    AlreadyExists,
    Conflict,
    DomainError,
    InvalidValue,
    NotAuthenticated,
    NotFound,
)

logger = logging.getLogger(__name__)

# Порядок важен: подкласс с другим кодом ответа должен стоять выше своего родителя.
HTTP_STATUS: dict[type[DomainError], int] = {
    FileTooLarge: 413,
    UnsupportedFileFormat: 415,
    JobNotCancellable: 409,
    JobResultsUnavailable: 409,
    NotAuthenticated: 401,
    NotFound: 404,
    AlreadyExists: 409,
    Conflict: 409,
    InvalidValue: 422,
}


def error_body(code: str, message: str, details: dict[str, object]) -> dict[str, object]:
    """Единый формат ошибки из HLD 10."""
    return {"code": code, "message": message, "details": details}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        status = next((code for kind, code in HTTP_STATUS.items() if isinstance(exc, kind)), 400)
        body = error_body(exc.code, exc.message, exc.details)
        logger.info(
            "Domain error",
            extra={
                "event": "http.request.domain_error",
                "error_code": exc.code,
                "status_code": status,
            },
        )
        return JSONResponse(status_code=status, content=body)

    @app.exception_handler(RequestValidationError)
    async def handle_invalid_request(_: Request, exc: RequestValidationError) -> JSONResponse:
        # F_Valid_2: поле и причина. error["msg"] приходит от pydantic на английском.
        fields = [
            {"field": ".".join(str(part) for part in error["loc"][1:]), "reason": error["msg"]}
            for error in exc.errors()
        ]
        logger.warning(
            "Request validation failed",
            extra={
                "event": "http.request.validation_error",
                "error_code": "VALIDATION_ERROR",
                "status_code": 422,
            },
        )
        return JSONResponse(
            status_code=422,
            content=error_body(
                "VALIDATION_ERROR", "Проверьте введённые данные", {"fields": fields}
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "Unhandled HTTP exception",
            exc_info=(type(exc), exc, exc.__traceback__),
            extra={
                "event": "http.request.unhandled_error",
                "request_id": request.state.request_id,
                "error_code": "INTERNAL_ERROR",
                "exception_type": type(exc).__name__,
                "status_code": 500,
            },
        )
        return JSONResponse(
            status_code=500,
            content=error_body("INTERNAL_ERROR", "Внутренняя ошибка сервера", {}),
            headers={"X-Request-ID": request.state.request_id},
        )
