from fastapi import FastAPI

from app import __version__
from app.api.routes import health

app = FastAPI(title="Generador de Códigos de Barras", version=__version__)
app.include_router(health.router)
