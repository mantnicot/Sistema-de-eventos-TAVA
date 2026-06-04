import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("tava.api")


def _error_body(
    *,
    error_type: str,
    code: str,
    message: str,
    status_code: int,
    details: Any = None,
) -> dict:
    body: dict = {
        "error_type": error_type,  # "user" | "system"
        "code": code,
        "message": message,
        "status": status_code,
    }
    if details is not None:
        body["details"] = details
    return body


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "error_type" in detail:
            body = detail
        elif exc.status_code in (401, 403, 404, 409, 422):
            body = _error_body(
                error_type="user",
                code="HTTP_ERROR",
                message=str(detail),
                status_code=exc.status_code,
            )
        else:
            body = _error_body(
                error_type="system" if exc.status_code >= 500 else "user",
                code="HTTP_ERROR",
                message=str(detail),
                status_code=exc.status_code,
            )
        logger.warning(
            "HTTP %s %s -> %s (%s)",
            request.method,
            request.url.path,
            exc.status_code,
            body.get("message"),
        )
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.info("Validación fallida %s %s: %s", request.method, request.url.path, exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body(
                error_type="user",
                code="VALIDATION_ERROR",
                message="Revisa los datos del formulario",
                status_code=422,
                details=exc.errors(),
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Error no controlado %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(
                error_type="system",
                code="INTERNAL_ERROR",
                message="Error interno del servidor. Intenta de nuevo en unos minutos.",
                status_code=500,
            ),
        )


def user_error(status_code: int, code: str, message: str) -> JSONResponse:
    from fastapi import HTTPException

    raise HTTPException(
        status_code=status_code,
        detail=_error_body(
            error_type="user",
            code=code,
            message=message,
            status_code=status_code,
        ),
    )
