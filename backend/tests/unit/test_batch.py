import csv
import io

from app.services.batch import (
    REPORT_HEADER,
    RowStatus,
    batch_limits,
    build_report_csv,
    validate_batch,
)
from app.services.excel_reader import SheetRow
from app.symbologies.base import OutputFormat
from app.symbologies.registry import registry

EAN13 = registry.get("ean13")


def sheet_row(
    row: int, code: str | None, name: str | None = None, error: str | None = None
) -> SheetRow:
    return SheetRow(row=row, input=code or "", code=code, error=error, name=name)


def test_valid_rows_are_normalized_and_named_by_code() -> None:
    report = validate_batch(EAN13, [sheet_row(2, "786-1234-56789"), sheet_row(3, "4006381333931")])

    assert [(r.status, r.normalized, r.filename, r.message) for r in report.rows] == [
        (RowStatus.OK, "7861234567898", "7861234567898", ""),
        (RowStatus.OK, "4006381333931", "4006381333931", ""),
    ]
    assert report.summary.valid == 2


def test_invalid_rows_carry_the_domain_message() -> None:
    report = validate_batch(
        EAN13,
        [
            sheet_row(2, "7861234567897"),
            sheet_row(3, "12AB"),
            sheet_row(4, None, error="Falta el código."),
        ],
    )

    assert [(r.status, r.message) for r in report.rows] == [
        (RowStatus.ERROR, "El dígito de control debe ser 8."),
        (
            RowStatus.ERROR,
            "El código solo puede contener dígitos (se permiten espacios y guiones).",
        ),
        (RowStatus.ERROR, "Falta el código."),
    ]
    assert all(r.filename is None for r in report.rows)


def test_duplicates_are_detected_after_normalization() -> None:
    report = validate_batch(
        EAN13,
        [
            sheet_row(2, "7861234567898"),
            sheet_row(3, "786123456789"),
            sheet_row(4, "786-1234-56789-8"),
        ],
    )

    first, *duplicates = report.rows
    assert first.status is RowStatus.OK
    for duplicate in duplicates:
        assert duplicate.status is RowStatus.DUPLICATE
        assert duplicate.normalized == "7861234567898"
        assert duplicate.filename is None
        assert duplicate.message == "Repetido de la fila 2: se genera una sola vez."
    assert report.summary.duplicates == 2


def test_custom_names_are_sanitized_and_deduplicated() -> None:
    report = validate_batch(
        EAN13,
        [
            sheet_row(2, "7861234567898", "../../x"),
            sheet_row(3, "4006381333931", "Leche"),
            sheet_row(4, "5901234123457", "leche"),
            sheet_row(5, "9780306406157", "..."),
            sheet_row(6, "0000000000000", "  galletas.png "),
        ],
    )

    assert [(r.filename, r.message) for r in report.rows] == [
        ("___x", "Nombre ajustado a «___x»."),
        ("Leche", ""),
        ("leche_2", "Nombre repetido: el archivo se llama «leche_2»."),
        ("9780306406157", "El nombre de archivo no es válido; se usa el código."),
        ("galletas", "Nombre ajustado a «galletas»."),
    ]


def test_a_custom_name_can_collide_with_a_code_name() -> None:
    report = validate_batch(
        EAN13, [sheet_row(2, "7861234567898"), sheet_row(3, "4006381333931", "7861234567898")]
    )

    assert [r.filename for r in report.rows] == ["7861234567898", "7861234567898_2"]


def test_summary_counts_every_status() -> None:
    report = validate_batch(
        EAN13,
        [sheet_row(2, "7861234567898"), sheet_row(3, "7861234567898"), sheet_row(4, "1")],
    )

    assert report.summary.total == 3
    assert (report.summary.valid, report.summary.errors, report.summary.duplicates) == (1, 1, 1)
    assert [r.row for r in report.valid_rows] == [2]


def test_report_csv_lists_all_rows_with_bom_and_formula_protection() -> None:
    report = validate_batch(
        EAN13,
        [
            sheet_row(2, "7861234567898", '=HYPERLINK("http://x")'),
            sheet_row(3, "+5"),
            sheet_row(4, "7861234567898"),
        ],
    )

    data = build_report_csv(report, [OutputFormat.PNG, OutputFormat.EPS])

    assert data.startswith("﻿".encode())
    rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))
    assert rows[0] == REPORT_HEADER
    assert rows[1][3] == "ok"
    # The file cell starts with "png/", so even a name like "=HYPERLINK(...)" is inert.
    assert rows[1][5].startswith("png/")
    assert rows[2][1] == "'+5"
    assert rows[3][3] == "duplicado"
    assert len(rows) == 4


def test_batch_limits_shrink_only_for_large_pngs() -> None:
    from app.symbologies.base import RenderOptions

    both = [OutputFormat.PNG, OutputFormat.EPS]
    assert batch_limits(EAN13, both, RenderOptions(scale=1), 500).max_rows == 500
    assert batch_limits(EAN13, both, RenderOptions(scale=5, dpi=300), 500).max_rows == 500
    big = batch_limits(EAN13, both, RenderOptions(scale=5, dpi=600), 500)
    assert (big.max_rows, big.png_width_px, big.png_height_px) == (241, 4446, 930)
    assert (
        batch_limits(EAN13, [OutputFormat.EPS], RenderOptions(scale=5, dpi=600), 500).max_rows
        == 500
    )
    assert batch_limits(EAN13, both, RenderOptions(scale=1), 50).max_rows == 50
