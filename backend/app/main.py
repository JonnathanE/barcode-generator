from typing import cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from starlette.types import ExceptionHandler

from app import __version__
from app.api.error_handlers import register_error_handlers
from app.api.routes import barcodes, health
from app.core.config import get_settings
from app.core.logging import configure_logging, log_requests
from app.core.rate_limit import limiter, rate_limit_exceeded_handler

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title="Generador de Códigos de Barras",
    version=__version__,
    description="Genera códigos de barras EAN-13 en PNG y EPS vectorial.",
)

app.middleware("http")(log_requests)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
    # The front reads the file name for downloads.
    expose_headers=["Content-Disposition"],
)

app.state.limiter = limiter
register_error_handlers(app)
app.add_exception_handler(RateLimitExceeded, cast(ExceptionHandler, rate_limit_exceeded_handler))

app.include_router(health.router)
app.include_router(barcodes.router)
