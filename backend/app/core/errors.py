"""Application errors serialized as ``{"error": {"code", "message", "details"}}``."""

from enum import StrEnum
from http import HTTPStatus
from typing import Any


class ErrorCode(StrEnum):
    INVALID_CHARACTERS = "INVALID_CHARACTERS"
    INVALID_LENGTH = "INVALID_LENGTH"
    INVALID_CHECK_DIGIT = "INVALID_CHECK_DIGIT"
    UNSUPPORTED_SYMBOLOGY = "UNSUPPORTED_SYMBOLOGY"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    TOO_MANY_ROWS = "TOO_MANY_ROWS"
    INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
    CODE_COLUMN_NOT_FOUND = "CODE_COLUMN_NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    RENDER_FAILED = "RENDER_FAILED"
    INVALID_REQUEST = "INVALID_REQUEST"
    NOT_FOUND = "NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"


_STATUS_BY_CODE: dict[ErrorCode, HTTPStatus] = {
    ErrorCode.INVALID_CHARACTERS: HTTPStatus.UNPROCESSABLE_ENTITY,
    ErrorCode.INVALID_LENGTH: HTTPStatus.UNPROCESSABLE_ENTITY,
    ErrorCode.INVALID_CHECK_DIGIT: HTTPStatus.UNPROCESSABLE_ENTITY,
    ErrorCode.UNSUPPORTED_SYMBOLOGY: HTTPStatus.NOT_FOUND,
    ErrorCode.UNSUPPORTED_FORMAT: HTTPStatus.UNPROCESSABLE_ENTITY,
    ErrorCode.FILE_TOO_LARGE: HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
    ErrorCode.TOO_MANY_ROWS: HTTPStatus.UNPROCESSABLE_ENTITY,
    ErrorCode.INVALID_FILE_TYPE: HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
    ErrorCode.CODE_COLUMN_NOT_FOUND: HTTPStatus.UNPROCESSABLE_ENTITY,
    ErrorCode.RATE_LIMITED: HTTPStatus.TOO_MANY_REQUESTS,
    ErrorCode.RENDER_FAILED: HTTPStatus.INTERNAL_SERVER_ERROR,
    ErrorCode.INVALID_REQUEST: HTTPStatus.UNPROCESSABLE_ENTITY,
    ErrorCode.NOT_FOUND: HTTPStatus.NOT_FOUND,
    ErrorCode.INTERNAL_ERROR: HTTPStatus.INTERNAL_SERVER_ERROR,
}


class AppError(Exception):
    """Expected error with a stable code and a message for the end user (Spanish)."""

    def __init__(self, code: ErrorCode, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    @property
    def status_code(self) -> int:
        return _STATUS_BY_CODE[self.code]

    def to_dict(self) -> dict[str, Any]:
        return error_body(self.code, self.message, self.details)


def error_body(
    code: ErrorCode, message: str, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}
