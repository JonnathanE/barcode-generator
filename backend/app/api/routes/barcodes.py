import logging

from fastapi import APIRouter, Query, Request, Response
from starlette.concurrency import run_in_threadpool

from app.core.errors import AppError, ErrorCode
from app.core.rate_limit import limiter, single_limit
from app.schemas.barcodes import RenderRequest, SymbologyOut, ValidateRequest, ValidateResponse
from app.schemas.errors import error_responses
from app.services.renderer import RenderError, render
from app.symbologies.registry import registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["barcodes"])


@router.get("/symbologies")
async def list_symbologies() -> list[SymbologyOut]:
    return [
        SymbologyOut(id=s.id, name=s.name, formats=sorted(s.supported_formats))
        for s in registry.all()
    ]


@router.post(
    "/barcodes/{symbology}/validate",
    responses=error_responses(404, 422, 429),
)
@limiter.limit(single_limit)
async def validate_code(
    request: Request,  # required by slowapi to read the client IP
    symbology: str,
    body: ValidateRequest,
) -> ValidateResponse:
    normalized = registry.get(symbology).normalize(body.code)
    return ValidateResponse(valid=True, normalized=normalized, check_digit=int(normalized[-1]))


@router.post(
    "/barcodes/{symbology}/render",
    response_class=Response,
    responses={
        200: {
            "content": {"image/png": {}, "application/postscript": {}},
            "description": "Archivo PNG o EPS.",
        },
        **error_responses(404, 422, 429, 500),
    },
)
@limiter.limit(single_limit)
async def render_code(
    request: Request,  # required by slowapi to read the client IP
    symbology: str,
    body: RenderRequest,
    inline: bool = Query(False, description="`true` para la vista previa (sin descarga)."),
) -> Response:
    resolved = registry.get(symbology)
    if body.format not in resolved.supported_formats:
        raise AppError(
            ErrorCode.UNSUPPORTED_FORMAT,
            f"{resolved.name} no se puede generar en formato {body.format.upper()}.",
            {"supported": sorted(resolved.supported_formats)},
        )
    code = resolved.normalize(body.code)

    try:
        # Ghostscript is a blocking subprocess: keep it off the event loop (RNF-04).
        content = await run_in_threadpool(
            render, resolved, code, body.format, body.options.to_domain()
        )
    except RenderError:
        # No traceback or Ghostscript output: its operand stack dump can contain the
        # hex-encoded code (RNF-13).
        logger.error("render_failed", extra={"symbology": resolved.id, "format": body.format})
        raise AppError(
            ErrorCode.RENDER_FAILED, "No se pudo generar el código de barras. Intenta de nuevo."
        ) from None

    disposition = "inline" if inline else "attachment"
    return Response(
        content=content,
        media_type=body.format.media_type,
        headers={"Content-Disposition": f'{disposition}; filename="{code}.{body.format}"'},
    )
