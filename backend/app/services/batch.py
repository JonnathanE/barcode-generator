"""Batch validation (RF-12, RF-16, RF-17) and ZIP generation (RF-14, RF-15)."""

import csv
import io
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from app.core.errors import AppError
from app.domain.filenames import FilenameAllocator, sanitize
from app.services.excel_reader import SheetRow
from app.services.renderer import render_many
from app.symbologies.base import OutputFormat, RenderOptions, Symbology

REPORT_FILENAME = "reporte.csv"
REPORT_HEADER = ["fila", "valor_original", "codigo", "estado", "mensaje", "archivo"]
# Excel runs cells starting with these as formulas (CSV injection).
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
# PNG is already compressed: deflating it again only burns CPU (0.1 CPU on Render).
_COMPRESSION = {OutputFormat.PNG: zipfile.ZIP_STORED, OutputFormat.EPS: zipfile.ZIP_DEFLATED}


class RowStatus(StrEnum):
    OK = "ok"
    ERROR = "error"
    DUPLICATE = "duplicado"


@dataclass(frozen=True, slots=True)
class BatchRow:
    row: int
    input: str
    normalized: str | None
    status: RowStatus
    message: str
    filename: str | None
    """Base name inside the ZIP (without extension); only for rows that are generated."""


@dataclass(frozen=True, slots=True)
class BatchSummary:
    total: int
    valid: int
    errors: int
    duplicates: int


@dataclass(frozen=True, slots=True)
class BatchReport:
    summary: BatchSummary
    rows: list[BatchRow]

    @property
    def valid_rows(self) -> list[BatchRow]:
        return [row for row in self.rows if row.status is RowStatus.OK]


def validate_batch(symbology: Symbology, sheet_rows: Sequence[SheetRow]) -> BatchReport:
    """Per-row report without rendering anything (RF-12)."""
    allocator = FilenameAllocator()
    first_row_by_code: dict[str, int] = {}
    rows: list[BatchRow] = []

    for sheet_row in sheet_rows:
        if sheet_row.error is not None or sheet_row.code is None:
            rows.append(_error(sheet_row, sheet_row.error or "Falta el código."))
            continue
        try:
            normalized = symbology.normalize(sheet_row.code)
        except AppError as exc:
            rows.append(_error(sheet_row, exc.message))
            continue

        if normalized in first_row_by_code:
            rows.append(
                BatchRow(
                    row=sheet_row.row,
                    input=sheet_row.input,
                    normalized=normalized,
                    status=RowStatus.DUPLICATE,
                    message=(
                        f"Repetido de la fila {first_row_by_code[normalized]}: "
                        "se genera una sola vez."
                    ),
                    filename=None,
                )
            )
            continue
        first_row_by_code[normalized] = sheet_row.row

        message = ""
        base = normalized
        if sheet_row.name is not None:
            safe = sanitize(sheet_row.name)
            if safe is None:
                message = "El nombre de archivo no es válido; se usa el código."
            else:
                base = safe
        filename = allocator.allocate(base)
        if filename != base and not message:
            message = f"Nombre repetido: el archivo se llama «{filename}»."
        elif sheet_row.name is not None and filename != sheet_row.name.strip() and not message:
            message = f"Nombre ajustado a «{filename}»."

        rows.append(
            BatchRow(
                row=sheet_row.row,
                input=sheet_row.input,
                normalized=normalized,
                status=RowStatus.OK,
                message=message,
                filename=filename,
            )
        )

    statuses = [row.status for row in rows]
    summary = BatchSummary(
        total=len(rows),
        valid=statuses.count(RowStatus.OK),
        errors=statuses.count(RowStatus.ERROR),
        duplicates=statuses.count(RowStatus.DUPLICATE),
    )
    return BatchReport(summary=summary, rows=rows)


def build_zip(
    symbology: Symbology,
    report: BatchReport,
    formats: Sequence[OutputFormat],
    options: RenderOptions,
) -> bytes:
    """ZIP with ``png/``, ``eps/`` and ``reporte.csv``, built in memory (RF-15, RNF-07).

    Blocking (Ghostscript): call it from a threadpool.
    """
    valid = report.valid_rows
    codes = [row.normalized for row in valid if row.normalized is not None]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for fmt in sorted(set(formats), key=list(OutputFormat).index):
            files = render_many(symbology, codes, fmt, options)
            for row, content in zip(valid, files, strict=True):
                archive.writestr(
                    f"{fmt}/{row.filename}.{fmt}", content, compress_type=_COMPRESSION[fmt]
                )
        archive.writestr(
            REPORT_FILENAME, build_report_csv(report, formats), compress_type=zipfile.ZIP_DEFLATED
        )
    return buffer.getvalue()


def build_report_csv(report: BatchReport, formats: Sequence[OutputFormat]) -> bytes:
    """All rows with their status (RF-15). UTF-8 with BOM so Excel shows accents."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(REPORT_HEADER)
    for row in report.rows:
        files = " ".join(f"{fmt}/{row.filename}.{fmt}" for fmt in formats) if row.filename else ""
        writer.writerow(
            [
                row.row,
                _safe_cell(row.input),
                row.normalized or "",
                row.status,
                _safe_cell(row.message),
                _safe_cell(files),
            ]
        )
    return ("﻿" + output.getvalue()).encode("utf-8")


def _error(sheet_row: SheetRow, message: str) -> BatchRow:
    return BatchRow(
        row=sheet_row.row,
        input=sheet_row.input,
        normalized=None,
        status=RowStatus.ERROR,
        message=message,
        filename=None,
    )


def _safe_cell(value: str) -> str:
    return f"'{value}" if value.startswith(_FORMULA_PREFIXES) else value
