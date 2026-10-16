import logging
import time
from datetime import UTC, datetime
from functools import cache
from typing import Annotated

from fastapi import APIRouter, File, Form, Request, Response, UploadFile
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.core.rate_limit import batch_limit, limiter, single_limit
from app.schemas.barcodes import RenderOptionsIn
from app.schemas.batch import (
    BatchLimitsRequest,
    BatchLimitsResponse,
    BatchRowOut,
    BatchSummaryOut,
    BatchValidateResponse,
)
from app.schemas.errors import error_responses
from app.services.batch import BatchReport, batch_limits, build_zip, validate_batch
from app.services.excel_reader import read_sheet
from app.services.renderer import RenderError
from app.services.template import TEMPLATE_FILENAME, build_template
from app.symbologies.base import OutputFormat, Symbology
from app.symbologies.registry import registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/batch", tags=["batch"])

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

ExcelFile = Annotated[UploadFile, File(description="Archivo .xlsx (se lee la primera hoja).")]
RestoreLeadingZeros = Annotated[
    bool,
    Form(
        description="Completar con ceros a la izquierda los números de 11 o 12 dígitos "
        "(Excel quita los ceros iniciales de las celdas numéricas)."
    ),
]


@cache
def _template() -> bytes:
    return build_template()


@router.get(
    "/template",
    response_class=Response,
    responses={200: {"content": {XLSX_MEDIA_TYPE: {}}, "description": "Plantilla .xlsx."}},
)
@limiter.limit(single_limit)
async def download_template(
    request: Request,  # required by slowapi to read the client IP
) -> Response:
    return Response(
        content=_template(),
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{TEMPLATE_FILENAME}"'},
    )


@router.post("/{symbology}/limits", responses=error_responses(404, 422, 429))
@limiter.limit(single_limit)
async def get_batch_limits(
    request: Request,  # required by slowapi to read the client IP
    symbology: str,
    body: BatchLimitsRequest,
) -> BatchLimitsResponse:
    """Máximo de filas para estas opciones: los PNG muy grandes lo reducen (RF-19)."""
    resolved = registry.get(symbology)
    settings = get_settings()
    limits = batch_limits(resolved, body.formats, body.options.to_domain(), settings.max_batch_rows)
    return BatchLimitsResponse(
        max_rows=limits.max_rows,
        max_upload_mb=settings.max_upload_mb,
        png_width_px=limits.png_width_px,
        png_height_px=limits.png_height_px,
    )


@router.post(
    "/{symbology}/validate",
    responses=error_responses(404, 411, 413, 415, 422, 429),
)
@limiter.limit(batch_limit)
async def validate_batch_file(
    request: Request,  # required by slowapi to read the client IP
    symbology: str,
    file: ExcelFile,
    restore_leading_zeros: RestoreLeadingZeros = False,
) -> BatchValidateResponse:
    """Paso 1: reporte por fila sin generar imágenes (RF-12)."""
    resolved = registry.get(symbology)
    content = await file.read()
    start = time.perf_counter()
    report = await run_in_threadpool(_validate, resolved, content, restore_leading_zeros)
    _log("batch_validated", report, start)
    return _to_response(report)


@router.post(
    "/{symbology}/generate",
    response_class=Response,
    responses={
        200: {
            "content": {"application/zip": {}},
            "description": "ZIP con png/, eps/ y reporte.csv.",
        },
        **error_responses(404, 411, 413, 415, 422, 429, 500),
    },
)
@limiter.limit(batch_limit)
async def generate_batch_zip(
    request: Request,  # required by slowapi to read the client IP
    symbology: str,
    file: ExcelFile,
    formats: Annotated[list[OutputFormat], Form(description="Uno o más: png, eps.")],
    options: Annotated[
        str,
        Form(description="Opciones de render en JSON (mismas que /barcodes/render)."),
    ] = "{}",
    restore_leading_zeros: RestoreLeadingZeros = False,
) -> Response:
    """Paso 2: genera las filas válidas y devuelve un ZIP (RF-14, RF-15)."""
    resolved = registry.get(symbology)
    unsupported = sorted(set(formats) - resolved.supported_formats)
    if unsupported:
        raise AppError(
            ErrorCode.UNSUPPORTED_FORMAT,
            f"{resolved.name} no se puede generar en formato {unsupported[0].upper()}.",
            {"supported": sorted(resolved.supported_formats)},
        )
    render_options = _parse_options(options)
    content = await file.read()

    start = time.perf_counter()
    report = await run_in_threadpool(_validate, resolved, content, restore_leading_zeros)
    if report.summary.valid == 0:
        raise AppError(
            ErrorCode.INVALID_REQUEST,
            "El archivo no tiene códigos válidos para generar.",
            {"summary": _summary_dict(report)},
        )
    domain_options = render_options.to_domain()
    limits = batch_limits(resolved, formats, domain_options, get_settings().max_batch_rows)
    if report.summary.valid > limits.max_rows:
        raise AppError(
            ErrorCode.TOO_MANY_ROWS,
            f"Con estas opciones (PNG de {limits.png_width_px} x {limits.png_height_px} px) "
            f"puedes generar hasta {limits.max_rows} códigos por lote y el archivo tiene "
            f"{report.summary.valid}. Reduce la escala o el DPI, o genera solo EPS.",
            {
                "max_rows": limits.max_rows,
                "valid": report.summary.valid,
                "png_width_px": limits.png_width_px,
                "png_height_px": limits.png_height_px,
            },
        )
    try:
        # Ghostscript and ZIP compression are blocking: keep them off the event loop.
        archive = await run_in_threadpool(build_zip, resolved, report, formats, domain_options)
    except RenderError:
        # No Ghostscript output in logs: it can contain the hex-encoded codes (RNF-13).
        logger.error("batch_render_failed", extra={"rows": report.summary.valid})
        raise AppError(
            ErrorCode.RENDER_FAILED, "No se pudieron generar los códigos. Intenta de nuevo."
        ) from None

    _log("batch_generated", report, start, formats=sorted(formats), zip_bytes=len(archive))
    filename = f"codigos_{datetime.now(UTC):%Y%m%d-%H%M%S}.zip"
    return Response(
        content=archive,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _validate(symbology: Symbology, content: bytes, restore_leading_zeros: bool) -> BatchReport:
    settings = get_settings()
    rows = read_sheet(
        content,
        max_rows=settings.max_batch_rows,
        max_mb=settings.max_upload_mb,
        restore_leading_zeros=restore_leading_zeros,
    )
    return validate_batch(symbology, rows)


def _parse_options(raw: str) -> RenderOptionsIn:
    try:
        return RenderOptionsIn.model_validate_json(raw)
    except ValidationError as exc:
        fields = [
            {
                "field": ".".join(["options", *(str(p) for p in error["loc"])]),
                "message": error["msg"],
            }
            for error in exc.errors()
        ]
        raise AppError(
            ErrorCode.INVALID_REQUEST,
            "Las opciones de generación no son válidas.",
            {"fields": fields},
        ) from None


def _summary_dict(report: BatchReport) -> dict[str, int]:
    summary = report.summary
    return {
        "total": summary.total,
        "valid": summary.valid,
        "errors": summary.errors,
        "duplicates": summary.duplicates,
    }


def _to_response(report: BatchReport) -> BatchValidateResponse:
    return BatchValidateResponse(
        summary=BatchSummaryOut(**_summary_dict(report)),
        rows=[
            BatchRowOut(
                row=row.row,
                input=row.input,
                normalized=row.normalized,
                status=row.status,
                message=row.message,
                filename=row.filename,
            )
            for row in report.rows
        ],
    )


def _log(event: str, report: BatchReport, start: float, **extra: object) -> None:
    """Counts and timings only, never codes or file contents (RNF-13, RNF-24)."""
    logger.info(
        event,
        extra={
            **_summary_dict(report),
            "duration_ms": round((time.perf_counter() - start) * 1000, 1),
            **extra,
        },
    )
