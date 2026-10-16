"""Defensive HTTP headers for every API response."""

from collections.abc import Awaitable, Callable

from fastapi import Request, Response

# Swagger UI loads its scripts and styles from a CDN; everything else is data.
_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")
_API_CSP = "default-src 'none'; frame-ancestors 'none'"


async def add_security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    headers = response.headers
    headers.setdefault("X-Content-Type-Options", "nosniff")  # never reinterpret a PNG as HTML
    headers.setdefault("Referrer-Policy", "no-referrer")
    headers.setdefault("X-Frame-Options", "DENY")
    if not request.url.path.startswith(_DOCS_PATHS):
        headers.setdefault("Content-Security-Policy", _API_CSP)
    return response
