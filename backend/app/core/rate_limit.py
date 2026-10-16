"""Per-IP rate limiting (RNF-10) with slowapi, limits read from settings."""

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.errors import ErrorCode, error_body

# In-memory storage: a single instance on Render free, nothing to share.
# Behind Render's proxy the client IP comes from X-Forwarded-For (uvicorn --proxy-headers).
limiter = Limiter(key_func=get_remote_address)


def single_limit() -> str:
    """Evaluated per request, so tests and env changes apply without re-importing."""
    return get_settings().rate_limit_single


def batch_limit() -> str:
    return get_settings().rate_limit_batch


async def rate_limit_exceeded_handler(_: Request, exc: RateLimitExceeded) -> JSONResponse:
    retry_after = exc.limit.limit.get_expiry() if exc.limit else 60
    return JSONResponse(
        error_body(
            ErrorCode.RATE_LIMITED,
            "Demasiadas solicitudes. Espera un momento e intenta de nuevo.",
            {"retry_after_seconds": retry_after},
        ),
        status_code=429,
        headers={"Retry-After": str(retry_after)},
    )
