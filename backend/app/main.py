from fastapi import FastAPI

from app import __version__
from app.api.error_handlers import register_error_handlers
from app.api.routes import barcodes, health

app = FastAPI(
    title="Generador de Códigos de Barras",
    version=__version__,
    description="Genera códigos de barras EAN-13 en PNG y EPS vectorial.",
)
register_error_handlers(app)
app.include_router(health.router)
app.include_router(barcodes.router)
