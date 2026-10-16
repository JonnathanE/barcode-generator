from typing import Any

from pydantic import BaseModel, Field

from app.core.errors import ErrorCode


class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str = Field(examples=["El dígito de control debe ser 8."])
    details: dict[str, Any] = Field(examples=[{"expected": 8, "received": 7}])


class ErrorResponse(BaseModel):
    error: ErrorDetail


def error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI ``responses`` entries documenting the error format."""
    return {status: {"model": ErrorResponse} for status in status_codes}
