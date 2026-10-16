"""Map every error to ``{"error": {"code", "message", "details"}}`` without internals."""

import logging
from typing import cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ExceptionHandler

from app.core.errors import AppError, ErrorCode, error_body

logger = logging.getLogger(__name__)


async def _app_error(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(exc.to_dict(), status_code=exc.status_code)


async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Drop "input"/"ctx": they echo user data and internal details.
    fields = [
        {"field": ".".join(str(part) for part in error["loc"]), "message": error["msg"]}
        for error in exc.errors()
    ]
    return JSONResponse(
        error_body(
            ErrorCode.INVALID_REQUEST, "La solicitud tiene datos inválidos.", {"fields": fields}
        ),
        status_code=422,
    )


async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    if exc.status_code == 404:
        body = error_body(ErrorCode.NOT_FOUND, "El recurso solicitado no existe.")
    else:
        body = error_body(ErrorCode.INVALID_REQUEST, str(exc.detail))
    return JSONResponse(body, status_code=exc.status_code, headers=exc.headers)


async def _unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_error", exc_info=exc)
    return JSONResponse(
        error_body(ErrorCode.INTERNAL_ERROR, "Ocurrió un error inesperado. Intenta de nuevo."),
        status_code=500,
    )


def register_error_handlers(app: FastAPI) -> None:
    # Starlette types handlers as taking any Exception; each one only receives its class.
    handlers: dict[type[Exception], object] = {
        AppError: _app_error,
        RequestValidationError: _validation_error,
        StarletteHTTPException: _http_error,
        Exception: _unexpected_error,
    }
    for exc_class, handler in handlers.items():
        app.add_exception_handler(exc_class, cast(ExceptionHandler, handler))
