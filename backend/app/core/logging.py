"""Structured JSON logs (RNF-24). Never log user codes or file contents (RNF-13)."""

import json
import logging
import sys
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import Request, Response

# Attributes every LogRecord has; anything else was passed through ``extra=``.
_RECORD_ATTRIBUTES = set(vars(logging.makeLogRecord({}))) | {"message", "asctime", "taskName"}
# Uvicorn adds an ANSI-colored copy of the message.
_IGNORED_EXTRAS = {"color_message"}

request_logger = logging.getLogger("app.request")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(
            {
                key: value
                for key, value in vars(record).items()
                if key not in _RECORD_ATTRIBUTES and key not in _IGNORED_EXTRAS
            }
        )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: str) -> None:
    """Send app and uvicorn logs through one JSON handler on stdout."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())

    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True

    # log_requests replaces the access log, which would print raw URLs.
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers = []
    access_logger.propagate = False


async def log_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """One log line per request: method, route template, status and duration."""
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route = request.scope.get("route")
        request_logger.info(
            "request",
            extra={
                "method": request.method,
                # Template ("/api/v1/barcodes/{symbology}/render"), never the raw URL or query.
                "endpoint": getattr(route, "path", "unmatched"),
                "status": status,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
            },
        )
