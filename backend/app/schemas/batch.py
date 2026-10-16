from pydantic import BaseModel, Field

from app.schemas.barcodes import RenderOptionsIn
from app.services.batch import RowStatus
from app.symbologies.base import OutputFormat


class BatchRowOut(BaseModel):
    row: int = Field(description="Número de fila en Excel.", examples=[2])
    input: str = Field(description="Valor original de la celda.", examples=["786123456789"])
    normalized: str | None = Field(examples=["7861234567898"])
    status: RowStatus
    message: str = Field(examples=["El dígito de control debe ser 8."])
    filename: str | None = Field(
        description="Nombre del archivo en el ZIP (sin extensión); solo filas válidas.",
        examples=["leche-entera"],
    )


class BatchSummaryOut(BaseModel):
    total: int
    valid: int
    errors: int
    duplicates: int


class BatchValidateResponse(BaseModel):
    summary: BatchSummaryOut
    rows: list[BatchRowOut]


class BatchLimitsRequest(BaseModel):
    formats: list[OutputFormat] = Field(min_length=1, examples=[["png", "eps"]])
    options: RenderOptionsIn = Field(default_factory=RenderOptionsIn)


class BatchLimitsResponse(BaseModel):
    max_rows: int = Field(description="Filas válidas que se pueden generar con estas opciones.")
    max_upload_mb: int
    png_width_px: int | None = Field(description="Tamaño de cada PNG (si se pide PNG).")
    png_height_px: int | None
