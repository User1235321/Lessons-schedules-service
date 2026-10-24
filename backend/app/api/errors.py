from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain.shared.errors import (
    AlreadyExists,
    DomainError,
    InvalidValue,
    NotAuthenticated,
    NotFound,
)

# Порядок важен: подкласс с другим кодом ответа должен стоять выше своего родителя.
HTTP_STATUS: dict[type[DomainError], int] = {
    NotAuthenticated: 401,
    NotFound: 404,
    AlreadyExists: 409,
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
        return JSONResponse(status_code=status, content=body)

    @app.exception_handler(RequestValidationError)
    async def handle_invalid_request(_: Request, exc: RequestValidationError) -> JSONResponse:
        # F_Valid_2: поле и причина. error["msg"] приходит от pydantic на английском.
        fields = [
            {"field": ".".join(str(part) for part in error["loc"][1:]), "reason": error["msg"]}
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_body(
                "VALIDATION_ERROR", "Проверьте введённые данные", {"fields": fields}
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, _exc: Exception) -> JSONResponse:
        # Starlette после ответа всё равно пробрасывает исключение дальше, в лог сервера.
        return JSONResponse(
            status_code=500,
            content=error_body("INTERNAL_ERROR", "Внутренняя ошибка сервера", {}),
        )
