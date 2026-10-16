"""Keep uploads in memory and reject oversized ones before parsing (RNF-03, RNF-07)."""

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.formparsers import MultiPartParser

from app.core.config import get_settings
from app.core.errors import ErrorCode, error_body
from app.services.excel_reader import BYTES_PER_MB

UPLOAD_PATH_PREFIX = "/api/v1/batch/"
# Room for the multipart boundaries and the small form fields next to the file.
MULTIPART_OVERHEAD_BYTES = 64 * 1024


def max_request_bytes() -> int:
    return get_settings().max_upload_mb * BYTES_PER_MB + MULTIPART_OVERHEAD_BYTES


def keep_uploads_in_memory() -> None:
    """Starlette spools files over 1 MB to a temp file on disk; Render's disk is
    ephemeral and the app must not write files. Every accepted request is smaller
    than this, so uploads stay in memory."""
    MultiPartParser.spool_max_size = max_request_bytes() + 1


async def limit_upload_size(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Reject by Content-Length before the body is read or parsed."""
    if request.method != "POST" or not request.url.path.startswith(UPLOAD_PATH_PREFIX):
        return await call_next(request)

    max_mb = get_settings().max_upload_mb
    length = request.headers.get("content-length")
    if length is None or not length.isdigit():
        return JSONResponse(
            error_body(ErrorCode.INVALID_REQUEST, "Falta el tamaño del archivo (Content-Length)."),
            status_code=411,
        )
    if int(length) > max_request_bytes():
        return JSONResponse(
            error_body(
                ErrorCode.FILE_TOO_LARGE,
                f"El archivo supera el límite de {max_mb} MB.",
                {"max_mb": max_mb},
            ),
            status_code=413,
        )
    return await call_next(request)
